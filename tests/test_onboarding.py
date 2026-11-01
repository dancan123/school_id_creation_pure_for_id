import io
import base64
import datetime
import pytest
from PIL import Image
from app import create_app
from config import TestConfig, Config
from extensions import db
from models import School, Student, User, SelfEnrolment, CardRecord, AdmissionAllowlist
from services.qr_service import QRService

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def setup_multi_schools(app):
    with app.app_context():
        school_a = School.query.filter_by(name="Alliance High School").first()
        if not school_a:
            school_a = School(
                name="Alliance High School",
                code="AHS-001",
                town="Kikuyu",
                county="Kiambu",
                primary_color="#1E3A8A",
                secondary_color="#F59E0B",
                academic_year="2026",
                allow_self_onboarding=True,
                auto_approve_onboarding=False
            )
            db.session.add(school_a)
            db.session.commit()
        else:
            school_a.allow_self_onboarding = True
            school_a.auto_approve_onboarding = False
            db.session.commit()

        school_b = School.query.filter_by(name="Mombasa Academy").first()
        if not school_b:
            school_b = School(
                name="Mombasa Academy",
                code="MSA-002",
                town="Mombasa",
                county="Mombasa",
                primary_color="#065F46",
                secondary_color="#D97706",
                academic_year="2026",
                allow_self_onboarding=True,
                auto_approve_onboarding=True # Auto-generate card on submission!
            )
            db.session.add(school_b)
            db.session.commit()

        for school_id, admission_number in [
            (school_a.id, "ADM-7788"),
            (school_a.id, "ADM-PREVIEW"),
            (school_a.id, "ADM-RETRY"),
            (school_a.id, "ADM-LATER"),
            (school_b.id, "MSA-5001"),
        ]:
            if not AdmissionAllowlist.query.filter_by(school_id=school_id, admission_number=admission_number).first():
                db.session.add(AdmissionAllowlist(
                    school_id=school_id,
                    admission_number=admission_number,
                    qr_token=f"TEST-{school_id}-{admission_number}",
                    is_active=True
                ))
        db.session.commit()

        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@school.ac.ke",
                full_name="System Admin",
                role="admin",
                school_id=school_a.id,
                is_active=True
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
        else:
            admin.set_password("admin123")
            admin.school_id = school_a.id
            db.session.commit()

        return school_a.id, school_b.id, admin.id

def test_public_onboarding_hub(client, setup_multi_schools):
    """Universal hub lists active schools and allows searching."""
    res = client.get("/onboard")
    assert res.status_code == 200
    assert b"Alliance High School" in res.data
    assert b"Mombasa Academy" in res.data

    # Search filter
    res_search = client.get("/onboard?q=Alliance")
    assert res_search.status_code == 200
    assert b"Alliance High School" in res_search.data

    # /enrol alias also works
    res_alias = client.get("/enrol")
    assert res_alias.status_code == 200

def test_school_specific_onboarding_page(client, setup_multi_schools):
    """Students can load school-specific onboarding via code or ID."""
    school_a_id, _, _ = setup_multi_schools

    # Via code
    res_code = client.get("/onboard/AHS-001")
    assert res_code.status_code == 200
    assert b"Alliance High School" in res_code.data
    assert b"Student ID Onboarding" in res_code.data

    # Case-insensitive code
    res_lower = client.get("/onboard/ahs-001")
    assert res_lower.status_code == 200

    # Via numeric ID
    res_id = client.get(f"/onboard/{school_a_id}")
    assert res_id.status_code == 200

    # /enrol/<code&gt; alias
    res_enrol = client.get("/enrol/AHS-001")
    assert res_enrol.status_code == 200

def test_api_check_admission(client, setup_multi_schools):
    """AJAX check-admission endpoint returns availability status."""
    school_a_id, _, _ = setup_multi_schools

    res = client.get(f"/api/check-admission?school_id={school_a_id}&admission_number=ADM-7788")
    assert res.status_code == 200
    data = res.get_json()
    assert data["available"] is True
    assert data["status"] == "available"

def test_student_self_onboarding_submission_workflow(client, setup_multi_schools, app):
    """Student submits onboarding with photo and details, receives tracking token."""
    school_a_id, _, _ = setup_multi_schools

    post_data = {
        "full_name": "Wycliffe Omondi Otieno",
        "admission_number": "ADM-7788",
        "curriculum_type": "CBC",
        "class_name": "Grade 8 (JSS 2)",
        "stream_name": "Simba",
        "academic_year": "2026",
        "gender": "Male",
        "dob": "2011-05-14",
        "blood_group": "O+",
        "parent_name": "Mary Otieno",
        "parent_phone": "+254 711 223344",
        "emergency_relationship": "Mother",
        "house_or_dorm": "Kilimanjaro House"
    }

    res = client.post("/onboard/AHS-001", data=post_data, follow_redirects=True)
    assert res.status_code == 200
    assert b"Onboarding Request Submitted!" in res.data
    assert b"ADM-7788" in res.data

    with app.app_context():
        sub = SelfEnrolment.query.filter_by(admission_number="ADM-7788").first()
        assert sub is not None
        assert sub.full_name == "Wycliffe Omondi Otieno"
        assert sub.status == "pending"
        assert sub.submission_token.startswith("ENR-")
        token = sub.submission_token

    res_track = client.get(f"/onboard/status/{token}")
    assert res_track.status_code == 200
    assert b"Wycliffe Omondi Otieno" in res_track.data

def test_auto_approve_school_instant_id_generation(client, setup_multi_schools, app):
    """For schools with auto_approve_onboarding=True, card is generated immediately."""
    _, school_b_id, _ = setup_multi_schools

    post_data = {
        "full_name": "Fatuma Ahmed Hassan",
        "admission_number": "MSA-5001",
        "curriculum_type": "844",
        "class_name": "Form 3",
        "stream_name": "North",
        "academic_year": "2026",
        "gender": "Female",
        "blood_group": "A+",
        "parent_name": "Ahmed Hassan",
        "parent_phone": "+254 722 998877"
    }

    res = client.post("/onboard/MSA-002", data=post_data, follow_redirects=True)
    assert res.status_code == 200
    assert b"ID Card Generated Automatically!" in res.data

    with app.app_context():
        sub = SelfEnrolment.query.filter_by(admission_number="MSA-5001").first()
        assert sub.status == "approved"
        assert sub.student_id is not None

        stud = Student.query.get(sub.student_id)
        assert stud.card_status == "active"
        assert stud.card_number is not None

        card = CardRecord.query.filter_by(student_id=stud.id).first()
        assert card is not None
        assert card.status == "active"
        assert card.single_pdf_filename is not None
        allow_entry = AdmissionAllowlist.query.filter_by(school_id=school_b_id, admission_number="MSA-5001").first()
        assert card.qr_token == allow_entry.qr_token

def test_school_qr_and_poster_endpoints(client, setup_multi_schools):
    """Tests the QR code and printable noticeboard poster generation."""
    # QR PNG
    res_qr = client.get("/onboard/qr/AHS-001")
    assert res_qr.status_code == 200
    assert res_qr.content_type == "image/png"
    assert len(res_qr.data) > 100

    # Noticeboard Poster
    res_poster = client.get("/onboard/poster/AHS-001")
    assert res_poster.status_code == 200
    assert b"STUDENT ID CARD ONBOARDING OPEN" in res_poster.data
    assert b"Alliance High School" in res_poster.data

def test_onboarding_link_can_be_closed_and_reopened(client, setup_multi_schools, app):
    """Closing the public link blocks both the form and submission endpoint."""
    school_a_id, _, _ = setup_multi_schools
    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

    close_res = client.post("/schools/settings", data={"onboarding_action": "disable"}, follow_redirects=True)
    assert close_res.status_code == 200
    closed_page = client.get("/onboard/AHS-001")
    assert closed_page.status_code == 403
    assert b"Online onboarding is currently closed" in closed_page.data

    submit_res = client.post("/onboard/AHS-001", data={
        "full_name": "Should Not Be Added",
        "admission_number": "CLOSED-001",
        "class_name": "Grade 7"
    })
    assert submit_res.status_code == 403
    with app.app_context():
        assert SelfEnrolment.query.filter_by(school_id=school_a_id, admission_number="CLOSED-001").first() is None

    open_res = client.post("/schools/settings", data={"onboarding_action": "enable"}, follow_redirects=True)
    assert open_res.status_code == 200
    assert client.get("/onboard/AHS-001").status_code == 200

def test_onboarding_public_host_mapping_in_settings_and_qr(client, setup_multi_schools, monkeypatch):
    """The configured public host is used in shared onboarding links and QR destinations."""
    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    settings_data = {
        "name": "Alliance High School", "code": "AHS-001", "motto": "", "po_box": "",
        "town": "Kikuyu", "county": "Kiambu", "phone": "", "email": "", "website": "",
        "primary_color": "#1E3A8A", "secondary_color": "#F59E0B", "accent_color": "#10B981",
        "text_color": "#0F172A", "principal_name": "", "card_prefix": "AHS-",
        "academic_year": "2026", "validity_years": "4", "disclaimer_text": "",
        "emergency_contact_phone": "", "auto_approve_onboarding": "0",
        "onboarding_instructions": "", "onboarding_base_url": "https://ids.example.org",
        "institution_type": "school", "principal_title": "", "card_title": "",
        "id_label": "", "class_label": "", "stream_label": "", "upi_label": "",
        "enable_watermark": "1"
    }
    save_res = client.post("/schools/settings", data=settings_data, follow_redirects=True)
    assert save_res.status_code == 200

    settings_res = client.get("/schools/settings")
    assert settings_res.status_code == 200
    assert b"https://ids.example.org" in settings_res.data

    captured = {}
    def fake_generate_qr(url, **kwargs):
        captured["url"] = url
        return b"test-png"
    monkeypatch.setattr(QRService, "generate_qr_png_bytes", fake_generate_qr)
    qr_res = client.get("/onboard/qr/AHS-001")
    assert qr_res.status_code == 200
    assert qr_res.content_type == "image/png"
    assert captured["url"].startswith("https://ids.example.org/")

def test_public_preview_uses_print_renderer_and_reserved_qr(client, setup_multi_schools, app):
    with app.app_context():
        school = School.query.filter_by(code="AHS-001").first()
        school.onboarding_base_url = "https://ids.example.org"
        eligible = AdmissionAllowlist.query.filter_by(admission_number="ADM-PREVIEW").first()
        reserved_token = eligible.qr_token
        db.session.commit()

    result = client.post("/onboard/AHS-001/preview", json={
        "full_name": "Preview Student",
        "admission_number": "ADM-PREVIEW",
        "class_name": "Grade 8",
        "academic_year": "2026"
    })
    assert result.status_code == 200
    payload = result.get_json()
    assert payload["card_number"].endswith("ADM-PREVIEW")
    for side in ("front", "back"):
        encoded = payload[side].split(",", 1)[1]
        image = Image.open(io.BytesIO(base64.b64decode(encoded)))
        assert image.size == (1011, 638)

    with app.app_context():
        school = School.query.filter_by(code="AHS-001").first()
        submission = SelfEnrolment(
            school_id=school.id, full_name="Preview Student", admission_number="ADM-PREVIEW",
            class_name="Grade 8", academic_year="2026", submission_token="ENR-PREVIEW",
            card_qr_token=reserved_token
        )
        db.session.add(submission)
        db.session.commit()
        assert submission.card_qr_token == reserved_token

def test_allowlisted_admission_can_submit_once_and_retry_rejection_once(client, setup_multi_schools, app):
    school_a_id, _, _ = setup_multi_schools
    payload = {
        "full_name": "Retry Applicant",
        "admission_number": "ADM-RETRY",
        "class_name": "Grade 7",
        "academic_year": "2026"
    }
    first = client.post("/onboard/AHS-001", data=payload, follow_redirects=True)
    assert first.status_code == 200
    assert b"Onboarding Request Submitted!" in first.data

    with app.app_context():
        submission = SelfEnrolment.query.filter_by(school_id=school_a_id, admission_number="ADM-RETRY").first()
        submission_id = submission.id
        token = submission.submission_token
        card_qr_token = submission.card_qr_token
        assert card_qr_token

    duplicate = client.post("/onboard/AHS-001", data=payload)
    assert duplicate.status_code == 200
    assert b"already under review" in duplicate.data
    with app.app_context():
        assert SelfEnrolment.query.filter_by(school_id=school_a_id, admission_number="ADM-RETRY").count() == 1

    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    client.post(f"/enrolment/{submission_id}/reject", data={"rejection_reason": "Please correct the photo."})
    status_page = client.get(f"/onboard/status/{token}")
    assert b"Correct details and resubmit once" in status_page.data

    retry = dict(payload, full_name="Retry Applicant Corrected")
    resubmitted = client.post("/onboard/AHS-001", data=retry, follow_redirects=True)
    assert resubmitted.status_code == 200
    with app.app_context():
        submission = db.session.get(SelfEnrolment, submission_id)
        assert submission.status == "pending"
        assert submission.full_name == "Retry Applicant Corrected"
        assert submission.resubmission_count == 1
        assert submission.submission_token == token
        assert SelfEnrolment.query.filter_by(school_id=school_a_id, admission_number="ADM-RETRY").count() == 1

    client.post(f"/enrolment/{submission_id}/reject", data={"rejection_reason": "Still needs admin help."})
    exhausted = client.post("/onboard/AHS-001", data=payload)
    assert exhausted.status_code == 200
    assert b"one permitted correction" in exhausted.data
    assert b"Contact the school administration" in exhausted.data

def test_delayed_card_generation_keeps_public_preview_qr_token(client, setup_multi_schools, app):
    school_a_id, _, _ = setup_multi_schools
    client.post("/onboard/AHS-001", data={
        "full_name": "Later Card Student", "admission_number": "ADM-LATER",
        "class_name": "Grade 6", "academic_year": "2026"
    }, follow_redirects=True)
    with app.app_context():
        allow_entry = AdmissionAllowlist.query.filter_by(school_id=school_a_id, admission_number="ADM-LATER").first()
        reserved_token = allow_entry.qr_token
        submission = SelfEnrolment.query.filter_by(school_id=school_a_id, admission_number="ADM-LATER").first()
        submission_id = submission.id

    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    approved = client.post(f"/enrolment/{submission_id}/approve", data={
        "full_name": "Later Card Student", "admission_number": "ADM-LATER",
        "class_name": "Grade 6", "curriculum_type": "CBC"
    }, follow_redirects=True)
    assert approved.status_code == 200

    with app.app_context():
        student = Student.query.filter_by(school_id=school_a_id, admission_number="ADM-LATER").first()
        assert student.pending_card_qr_token == reserved_token
        student_id = student.id

    generated = client.post("/single-id/generate", data={"student_id": str(student_id)}, follow_redirects=True)
    assert generated.status_code == 200
    with app.app_context():
        card = CardRecord.query.filter_by(student_id=student_id, status="active").first()
        assert card.qr_token == reserved_token
        assert db.session.get(Student, student_id).pending_card_qr_token is None

def test_admission_allowlist_admin_management_and_class_filter(client, setup_multi_schools, app):
    school_a_id, _, _ = setup_multi_schools
    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    added = client.post("/enrolment/admission-allowlist", data={"admission_numbers": "ADM-NEW-1, ADM-NEW-2\nADM-7788"}, follow_redirects=True)
    assert added.status_code == 200
    assert b"ADM-NEW-1" in added.data
    assert client.get(f"/api/check-admission?school_id={school_a_id}&admission_number=NOT-LISTED").get_json()["available"] is False

    with app.app_context():
        db.session.add_all([
            Student(school_id=school_a_id, admission_number="CLASS-7", full_name="Grade Seven Learner", class_name="Grade 7"),
            Student(school_id=school_a_id, admission_number="CLASS-8", full_name="Grade Eight Learner", class_name="Grade 8")
        ])
        db.session.commit()
    class_page = client.get("/students/?class=Grade%208")
    assert class_page.status_code == 200
    assert b"Grade Eight Learner" in class_page.data
    assert b"Grade Seven Learner" not in class_page.data

def test_admin_queue_and_card_review_approval(client, setup_multi_schools, app):
    """Admin logs in, reviews submission, and one-click approves & generates ID card."""
    school_a_id, _, admin_id = setup_multi_schools

    # Create pending enrolment
    with app.app_context():
        enrol = SelfEnrolment(
            school_id=school_a_id,
            full_name="Brian Kiprop Langat",
            admission_number="AHS-8800",
            curriculum_type="CBC",
            class_name="Grade 7 (JSS 1)",
            academic_year="2026",
            status="pending"
        )
        db.session.add(enrol)
        db.session.commit()
        enrol_id = enrol.id

    # Login as admin
    client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

    # View queue
    res_q = client.get("/enrolment/queue")
    assert res_q.status_code == 200
    assert b"Brian Kiprop Langat" in res_q.data
    assert b"Card ID Review" in res_q.data

    # Approve and generate card now
    res_app = client.post(
        f"/enrolment/{enrol_id}/approve",
        data={
            "full_name": "Brian Kiprop Langat",
            "admission_number": "AHS-8800",
            "class_name": "Grade 7 (JSS 1)",
            "curriculum_type": "CBC",
            "generate_now": "1"
        },
        follow_redirects=True
    )
    assert res_app.status_code == 200
    assert b"approved" in res_app.data.lower()

    with app.app_context():
        updated_enrol = SelfEnrolment.query.get(enrol_id)
        assert updated_enrol.status == "approved"
        assert updated_enrol.student_id is not None

        stud = Student.query.get(updated_enrol.student_id)
        assert stud.admission_number == "AHS-8800"
        assert stud.card_status == "active"
