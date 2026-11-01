"""
routes/enrolment.py
-------------------
Comprehensive Student Self-Onboarding and Card Review & Generation Engine.

Features:
1. Public Multi-School Hub & Directory:
   - /onboard & /enrol: Search and browse schools to self-onboard.
   - /onboard/<school_code> & /enrol/<school_code>: School-branded onboarding portal.
   - /onboard/status/<token>: Real-time status tracking for students.
   - /onboard/qr/<school_code>: Printable QR Code PNG for school noticeboards.
   - /onboard/poster/<school_code>: Printable A4 ID Onboarding announcement poster.
   - /api/check-admission: Real-time admission duplicate check.

2. Submission Tools:
   - Live Webcam / Camera viewfinder with facial framing guide.
   - Interactive Passport Cropper with zoom, pan, and rotation (standard 3:4 ratio).
   - Touch/Stylus/Mouse Digital Signature Canvas.
   - Real-time live card ID review (Front & Back simulation).

3. Admin Enrolment Queue:
   - /enrolment/queue: Review submissions with Card ID preview modal.
   - One-click "Approve & Generate ID Card Now": Instantly generates 300 DPI card images and CR80 PDF.
   - Batch approval & queue management.
"""
import datetime
import secrets
import base64
import binascii
import io
import re
from types import SimpleNamespace
from PIL import Image
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, jsonify, Response
)
from flask_login import login_required, current_user

from extensions import db
from models import School, Student, SelfEnrolment, CardRecord, AdmissionAllowlist
from config import Config
from utils import get_current_school, log_audit, save_uploaded_file, save_base64_image, build_public_url
from services.card_renderer import CardRenderer
from services.qr_service import QRService

enrolment_bp = Blueprint("enrolment", __name__)

# ── Kenyan CBC & 8-4-4 Class Configurations ────────────────────────────────────
CBC_CLASSES = [
    # Pre-Primary
    "Pre-Primary 1 (PP1)", "Pre-Primary 2 (PP2)",
    # Lower Primary
    "Grade 1", "Grade 2", "Grade 3",
    # Upper Primary
    "Grade 4", "Grade 5", "Grade 6",
    # Junior Secondary School (JSS)
    "Grade 7 (JSS 1)", "Grade 8 (JSS 2)", "Grade 9 (JSS 3)",
    # Senior Secondary School (SS)
    "Grade 10 (SS 1)", "Grade 11 (SS 2)", "Grade 12 (SS 3)",
]

OLD_844_CLASSES = [
    "Standard 1", "Standard 2", "Standard 3", "Standard 4",
    "Standard 5", "Standard 6", "Standard 7", "Standard 8",
    "Form 1", "Form 2", "Form 3", "Form 4",
    "Form 5", "Form 6",
]

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: Multi-School Onboarding Directory / Hub
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/onboard", methods=["GET"])
@enrolment_bp.route("/enrol", methods=["GET"])
def onboard_hub():
    """Universal Public Landing Hub for students & parents to find their school."""
    search = request.args.get("q", "").strip()
    query = School.query.filter_by(is_active=True, allow_self_onboarding=True)
    if search:
        query = query.filter(
            (School.name.ilike(f"%{search}%")) |
            (School.code.ilike(f"%{search}%")) |
            (School.county.ilike(f"%{search}%")) |
            (School.town.ilike(f"%{search}%"))
        )
    schools = query.order_by(School.name).all()

    return render_template(
        "enrolment/onboard_hub.html",
        schools=schools,
        search=search,
        total_schools=School.query.filter_by(is_active=True, allow_self_onboarding=True).count()
    )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: School-Specific Student Self-Onboarding Portal
# ─────────────────────────────────────────────────────────────────────────────

def _find_school_by_code_or_id(school_code):
    """Case-insensitive lookup for school code, ID, or fallback name."""
    s_code = str(school_code).strip()
    # Check numeric ID
    if s_code.isdigit():
        sch = School.query.filter_by(id=int(s_code), is_active=True).first()
        if sch:
            return sch

    # Check case-insensitive code
    sch = School.query.filter(
        db.func.lower(School.code) == s_code.lower(),
        School.is_active == True
    ).first()
    if sch:
        return sch

    # Fallback: check by exact code or name
    sch = School.query.filter(
        (School.code == s_code) | (School.name.ilike(f"%{s_code}%")),
        School.is_active == True
    ).first()
    return sch


@enrolment_bp.route("/onboard/<school_code>", methods=["GET", "POST"])
@enrolment_bp.route("/enrol/<school_code>", methods=["GET", "POST"])
def self_enrol(school_code):
    """Public intake portal for a specific school — no login required."""
    school = _find_school_by_code_or_id(school_code)
    if not school:
        # Suggest available schools
        all_schools = School.query.filter_by(is_active=True, allow_self_onboarding=True).order_by(School.name).all()
        return render_template(
            "enrolment/school_not_found.html",
            searched_code=school_code,
            available_schools=all_schools
        ), 404

    # Check if school has enabled online onboarding
    if hasattr(school, "allow_self_onboarding") and not school.allow_self_onboarding:
        return render_template(
            "enrolment/onboarding_closed.html",
            school=school
        ), 403

    if request.method == "POST":
        full_name       = request.form.get("full_name", "").strip()
        admission_no    = request.form.get("admission_number", "").strip().upper()
        curriculum_type = request.form.get("curriculum_type", "CBC").strip()
        class_name      = request.form.get("class_name", "").strip()
        stream_name     = request.form.get("stream_name", "").strip() or None
        academic_year   = request.form.get("academic_year", school.academic_year or str(datetime.date.today().year)).strip()
        gender          = request.form.get("gender", "").strip() or None
        dob             = request.form.get("dob", "").strip() or None
        nemis_upi       = request.form.get("nemis_upi", "").strip() or None
        blood_group     = request.form.get("blood_group", "").strip() or None
        house_or_dorm   = request.form.get("house_or_dorm", "").strip() or None
        medical_notes   = request.form.get("medical_notes", "").strip() or None

        parent_name     = request.form.get("parent_name", "").strip() or None
        parent_phone    = request.form.get("parent_phone", "").strip() or None
        emergency_rel   = request.form.get("emergency_relationship", "").strip() or None

        # Admission eligibility and duplicate protection
        errors = []
        if not full_name:
            errors.append("Student full name is required.")
        if not admission_no:
            errors.append("Admission number is required.")
        if not class_name:
            errors.append("Class / Grade is required.")

        eligibility = AdmissionAllowlist.query.filter_by(
            school_id=school.id, admission_number=admission_no
        ).with_for_update().first() if admission_no else None
        retry_submission = None
        if not eligibility or not eligibility.is_active:
            errors.append(f"Admission number '{admission_no}' is not authorized for online ID onboarding. Contact the school administration.")
        else:
            existing_submission = None
            if eligibility.current_enrolment_id:
                existing_submission = db.session.get(SelfEnrolment, eligibility.current_enrolment_id)
            if not existing_submission:
                existing_submission = SelfEnrolment.query.filter_by(
                    school_id=school.id, admission_number=admission_no
                ).order_by(SelfEnrolment.submitted_at.desc()).first()

            if existing_submission and existing_submission.status == "pending":
                errors.append(f"An application for admission '{admission_no}' is already under review. Check reference {existing_submission.submission_token} or contact the school administration.")
            elif existing_submission and existing_submission.status == "approved":
                errors.append(f"Admission '{admission_no}' has already been processed. Contact the school administration if you need help.")
            elif existing_submission and existing_submission.status == "rejected":
                if existing_submission.resubmission_count >= 1:
                    errors.append(f"The one permitted correction for admission '{admission_no}' has already been used. Contact the school administration.")
                else:
                    retry_submission = existing_submission

            already_registered = Student.query.filter_by(
                school_id=school.id, admission_number=admission_no, is_archived=False
            ).first()
            if already_registered:
                errors.append(f"Admission '{admission_no}' is already present in the student register. Contact the school administration.")

        if errors:
            return render_template(
                "enrolment/self_enrol.html",
                school=school,
                cbc_classes=CBC_CLASSES,
                old_classes=OLD_844_CLASSES,
                blood_groups=BLOOD_GROUPS,
                errors=errors,
                form=request.form
            )

        # Handle Passport Photo: Supports File Upload OR Base64 Cropped/Webcam Data
        photo_fn = None
        photo_cropped_data = request.form.get("photo_cropped_data", "").strip()
        webcam_data = request.form.get("webcam_image_data", "").strip()

        if photo_cropped_data and len(photo_cropped_data) > 50:
            photo_fn = save_base64_image(
                photo_cropped_data,
                Config.PHOTOS_DIR,
                prefix=f"photo_{school.id}_{admission_no}_"
            )
        elif webcam_data and len(webcam_data) > 50:
            photo_fn = save_base64_image(
                webcam_data,
                Config.PHOTOS_DIR,
                prefix=f"photo_{school.id}_{admission_no}_"
            )
        elif "photo_file" in request.files:
            pf = request.files["photo_file"]
            if pf and pf.filename:
                photo_fn = save_uploaded_file(
                    pf, Config.PHOTOS_DIR,
                    prefix=f"photo_{school.id}_{admission_no}_"
                )

        # Handle Digital Signature (Canvas base64 or file upload)
        signature_fn = None
        signature_data = request.form.get("signature_data", "").strip()
        if signature_data and len(signature_data) > 50:
            signature_fn = save_base64_image(
                signature_data,
                Config.SIGNATURES_DIR,
                prefix=f"sig_stud_{school.id}_{admission_no}_",
                default_ext=".png"
            )
        elif "signature_file" in request.files:
            sf = request.files["signature_file"]
            if sf and sf.filename:
                signature_fn = save_uploaded_file(
                    sf, Config.SIGNATURES_DIR,
                    prefix=f"sig_stud_{school.id}_{admission_no}_"
                )

        if errors:
            return render_template(
                "enrolment/self_enrol.html",
                school=school,
                cbc_classes=CBC_CLASSES,
                old_classes=OLD_844_CLASSES,
                blood_groups=BLOOD_GROUPS,
                errors=errors,
                form=request.form
            )

        # Reuse a rejected application once, rather than creating duplicate records.
        if retry_submission:
            enrolment = retry_submission
            enrolment.resubmission_count += 1
            enrolment.reviewed_by_user_id = None
            enrolment.reviewed_at = None
            enrolment.rejection_reason = None
            enrolment.submitted_at = datetime.datetime.utcnow()
        else:
            sub_token = f"ENR-{datetime.date.today().year}-{secrets.token_hex(3).upper()}"
            enrolment = SelfEnrolment(
                school_id=school.id,
                submission_token=sub_token,
                resubmission_count=0,
                status="pending"
            )
            db.session.add(enrolment)

        enrolment.full_name = full_name
        enrolment.admission_number = admission_no
        enrolment.curriculum_type = curriculum_type
        enrolment.class_name = class_name
        enrolment.stream_name = stream_name
        enrolment.academic_year = academic_year
        enrolment.gender = gender
        enrolment.dob = dob
        enrolment.nemis_upi = nemis_upi
        enrolment.parent_name = parent_name
        enrolment.parent_phone = parent_phone
        enrolment.emergency_relationship = emergency_rel
        enrolment.blood_group = blood_group
        enrolment.house_or_dorm = house_or_dorm
        enrolment.medical_notes = medical_notes
        enrolment.photo_filename = photo_fn or (retry_submission.photo_filename if retry_submission else None)
        enrolment.signature_filename = signature_fn or (retry_submission.signature_filename if retry_submission else None)
        enrolment.card_qr_token = eligibility.qr_token
        enrolment.status = "pending"
        enrolment.ip_address = request.remote_addr
        db.session.flush()
        eligibility.current_enrolment_id = enrolment.id
        sub_token = enrolment.submission_token

        # ── Auto-Approval Check ──────────────────────────────────────────────
        generated_card = None
        if getattr(school, "auto_approve_onboarding", False):
            # Create Student record immediately
            student = Student(
                school_id=school.id,
                admission_number=admission_no,
                full_name=full_name,
                curriculum_type=curriculum_type,
                class_name=class_name,
                stream_name=stream_name,
                academic_year=academic_year,
                gender=gender,
                dob=dob,
                nemis_upi=nemis_upi,
                parent_name=parent_name,
                parent_phone=parent_phone,
                blood_group=blood_group,
                house_or_dorm=house_or_dorm,
                photo_filename=photo_fn,
                photo_cropped_filename=photo_fn,
                signature_filename=signature_fn,
                card_status="pending",
                enrolment_status="verified",
                pending_card_qr_token=enrolment.card_qr_token,
            )
            db.session.add(student)
            db.session.flush()

            # Generate ID Card now
            base_url = build_public_url("", school).rstrip("/")
            generated_card = CardRenderer.generate_card_for_student(school, student, base_url, qr_token=enrolment.card_qr_token)

            enrolment.status = "approved"
            enrolment.student_id = student.id
            enrolment.reviewed_at = datetime.datetime.utcnow()

        db.session.commit()

        return render_template(
            "enrolment/self_enrol_success.html",
            school=school,
            enrolment=enrolment,
            generated_card=generated_card,
            tracking_url=build_public_url(url_for("enrolment.track_status", token=sub_token), school)
        )

    return render_template(
        "enrolment/self_enrol.html",
        school=school,
        cbc_classes=CBC_CLASSES,
        old_classes=OLD_844_CLASSES,
        blood_groups=BLOOD_GROUPS,
        errors=[],
        form={"admission_number": request.args.get("admission_number", "").strip().upper()}
    )


@enrolment_bp.route("/onboard/<school_code>/preview", methods=["POST"])
@enrolment_bp.route("/enrol/<school_code>/preview", methods=["POST"])
def preview_public_card(school_code):
    """Render applicant data using the exact same artwork pipeline as CR80 print files."""
    school = _find_school_by_code_or_id(school_code)
    if not school or not school.allow_self_onboarding:
        return jsonify({"error": "Online onboarding is currently closed."}), 403
    if request.content_length and request.content_length > 2_500_000:
        return jsonify({"error": "Preview request is too large."}), 413

    data = request.get_json(silent=True) or {}
    admission_number = str(data.get("admission_number", "")).strip().upper()[:50]
    eligibility = AdmissionAllowlist.query.filter_by(
        school_id=school.id, admission_number=admission_number, is_active=True
    ).first()
    if not eligibility:
        return jsonify({"error": "This admission number is not on the school's eligible list. Contact the school administration."}), 403

    previous = db.session.get(SelfEnrolment, eligibility.current_enrolment_id) if eligibility.current_enrolment_id else None
    if previous and (previous.status != "rejected" or previous.resubmission_count >= 1):
        return jsonify({"error": "This admission number has already used its online submission. Contact the school administration."}), 409
    if Student.query.filter_by(school_id=school.id, admission_number=admission_number, is_archived=False).first():
        return jsonify({"error": "This admission number is already in the student register. Contact the school administration."}), 409

    full_name = str(data.get("full_name", "")).strip()[:150]
    class_name = str(data.get("class_name", "")).strip()[:50]
    if not admission_number or not full_name or not class_name:
        return jsonify({"error": "Enter the student's name, eligible admission number, and class to preview the card."}), 400
    academic_year = str(data.get("academic_year") or school.academic_year or datetime.date.today().year).strip()[:4]
    if not academic_year.isdigit():
        academic_year = str(datetime.date.today().year)

    def decode_image(data_url, label):
        if not data_url:
            return None
        match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", str(data_url))
        if not match or len(match.group(1)) > 1_800_000:
            raise ValueError(f"{label} image is not a supported image or exceeds the preview limit.")
        try:
            raw = base64.b64decode(match.group(1), validate=True)
            image = Image.open(io.BytesIO(raw))
            if image.width * image.height > 10_000_000:
                raise ValueError(f"{label} image dimensions are too large.")
            image.load()
            return image.copy()
        except (binascii.Error, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"{label} image could not be read.") from exc

    try:
        photo = decode_image(data.get("photo_data"), "Passport photo")
        signature = decode_image(data.get("signature_data"), "Signature")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    student = SimpleNamespace(
        full_name=full_name,
        admission_number=admission_number,
        class_name=class_name,
        stream_name=str(data.get("stream_name", "")).strip()[:50] or None,
        academic_year=academic_year,
        blood_group=str(data.get("blood_group", "")).strip()[:10] or None,
        house_or_dorm=str(data.get("house_or_dorm", "")).strip()[:60] or None,
        parent_phone=str(data.get("parent_phone", "")).strip()[:50] or None,
        nemis_upi=str(data.get("nemis_upi", "")).strip()[:50] or None,
        photo_cropped_filename=None,
        photo_filename=None,
        signature_filename=None,
        preview_photo=photo,
        preview_signature=signature
    )
    expiry_date = datetime.date(int(academic_year) + (school.validity_years or 4), 12, 31)
    card = SimpleNamespace(
        card_number=f"{school.card_prefix or 'ID-'}{admission_number}",
        qr_token=eligibility.qr_token,
        expiry_date=expiry_date,
        renewal_count=0
    )

    def png_data_url(image):
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    try:
        verify_base = build_public_url("", school)
        front = CardRenderer.render_front(school, student, card)
        back = CardRenderer.render_back(school, student, card, verify_base_url=verify_base)
    except Exception:
        return jsonify({"error": "Card preview could not be rendered. Please contact the school administration."}), 500
    response = jsonify({"front": png_data_url(front), "back": png_data_url(back), "card_number": card.card_number})
    response.headers["Cache-Control"] = "no-store"
    return response


@enrolment_bp.route("/enrolment/admission-allowlist", methods=["GET", "POST"])
@login_required
def admission_allowlist():
    """School-admin tool for managing admission numbers eligible for public intake."""
    if current_user.role not in ("admin", "superadmin"):
        abort(403)

    school = get_current_school()
    if request.method == "POST":
        raw_numbers = request.form.get("admission_numbers", "")
        numbers = {line.strip().upper() for line in raw_numbers.replace(",", "\n").replace(";", "\n").splitlines() if line.strip()}
        added = 0
        skipped = 0
        for admission_number in sorted(numbers):
            if len(admission_number) > 50:
                skipped += 1
                continue
            existing_student = Student.query.filter_by(
                school_id=school.id,
                admission_number=admission_number,
                is_archived=False
            ).first()
            if existing_student:
                skipped += 1
                continue

            entry = AdmissionAllowlist.query.filter_by(
                school_id=school.id, admission_number=admission_number
            ).first()
            if entry:
                if not entry.is_active:
                    entry.is_active = True
                    added += 1
                else:
                    skipped += 1
                continue

            db.session.add(AdmissionAllowlist(
                school_id=school.id,
                admission_number=admission_number,
                qr_token=QRService.generate_unique_token(),
                created_by_user_id=current_user.id,
                is_active=True
            ))
            added += 1

        db.session.commit()
        flash(f"Added or reactivated {added} admission number(s); skipped {skipped} duplicate, registered, or invalid number(s).", "success" if added else "warning")
        log_audit("UPDATE_ADMISSION_ALLOWLIST", f"Added/reactivated {added}; skipped {skipped} admissions", school_id=school.id)
        return redirect(url_for("enrolment.admission_allowlist"))

    entries = AdmissionAllowlist.query.filter_by(school_id=school.id).order_by(AdmissionAllowlist.admission_number).all()
    entry_rows = [(entry, db.session.get(SelfEnrolment, entry.current_enrolment_id) if entry.current_enrolment_id else None) for entry in entries]
    return render_template("enrolment/admission_allowlist.html", current_school=school, entries=entry_rows)


@enrolment_bp.route("/enrolment/admission-allowlist/<int:entry_id>/deactivate", methods=["POST"])
@login_required
def deactivate_admission(entry_id):
    if current_user.role not in ("admin", "superadmin"):
        abort(403)
    school = get_current_school()
    entry = AdmissionAllowlist.query.filter_by(id=entry_id, school_id=school.id).first_or_404()
    entry.is_active = False
    db.session.commit()
    log_audit("DEACTIVATE_ALLOWLIST_ADMISSION", f"Deactivated admission {entry.admission_number}", school_id=school.id)
    flash(f"Admission {entry.admission_number} is no longer authorized for public onboarding.", "info")
    return redirect(url_for("enrolment.admission_allowlist"))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: Real-Time Onboarding Status Tracker
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/onboard/status/<token>", methods=["GET"])
@enrolment_bp.route("/enrol/status/<token>", methods=["GET"])
def track_status(token):
    """Students and parents can track their ID card creation status anytime."""
    enrolment = SelfEnrolment.query.filter_by(submission_token=token).first()

    if not enrolment:
        return render_template(
            "enrolment/status_lookup.html",
            error=f"No enrolment record found matching reference '{token}'. Please check the code and try again."
        )

    school = db.session.get(School, enrolment.school_id)
    student = db.session.get(Student, enrolment.student_id) if enrolment.student_id else None
    card = CardRecord.query.filter_by(student_id=student.id, status="active").first() if student else None
    eligibility = AdmissionAllowlist.query.filter_by(
        school_id=enrolment.school_id, admission_number=enrolment.admission_number, is_active=True
    ).first()
    can_resubmit = bool(
        school and school.allow_self_onboarding and enrolment.status == "rejected" and
        enrolment.resubmission_count < 1 and eligibility
    )

    return render_template(
        "enrolment/status_view.html",
        school=school,
        enrolment=enrolment,
        student=student,
        card=card,
        can_resubmit=can_resubmit,
        resubmit_url=url_for("enrolment.self_enrol", school_code=school.code or school.id, admission_number=enrolment.admission_number) if can_resubmit else None
    )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: Printable Onboarding QR Code & Poster
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/onboard/qr/<school_code>")
@enrolment_bp.route("/enrol/qr/<school_code>")
def get_school_qr(school_code):
    """Returns a direct PNG of the scannable onboarding QR code for this school."""
    school = _find_school_by_code_or_id(school_code)
    if not school:
        abort(404)

    target_path = url_for("enrolment.self_enrol", school_code=school.code or school.id)
    target_url = build_public_url(target_path, school)
    png_bytes = QRService.generate_qr_png_bytes(target_url, size_px=400, add_shield=True)

    return Response(
        png_bytes,
        mimetype="image/png",
        headers={"Content-Disposition": f"inline; filename=onboard_qr_{school.code or school.id}.png"}
    )


@enrolment_bp.route("/onboard/poster/<school_code>")
@enrolment_bp.route("/enrol/poster/<school_code>")
def print_poster(school_code):
    """Ready-to-print A4 ID Card Onboarding Poster for school noticeboards."""
    school = _find_school_by_code_or_id(school_code)
    if not school:
        abort(404)

    onboard_path = url_for("enrolment.self_enrol", school_code=school.code or school.id)
    onboard_url = build_public_url(onboard_path, school)
    return render_template(
        "enrolment/poster.html",
        school=school,
        onboard_url=onboard_url
    )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API: Real-Time Admission Number Availability Check
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/api/check-admission", methods=["GET"])
def check_admission():
    """AJAX helper used by the live onboarding form to avoid collisions."""
    school_id = request.args.get("school_id")
    adm_no = request.args.get("admission_number", "").strip().upper()

    if not school_id or not adm_no:
        return jsonify({"valid": False, "message": "Missing parameters."})

    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school or not school.allow_self_onboarding:
        return jsonify({"available": False, "status": "closed", "message": "Online onboarding is currently closed."}), 403

    eligibility = AdmissionAllowlist.query.filter_by(
        school_id=school.id, admission_number=adm_no, is_active=True
    ).first()
    if not eligibility:
        return jsonify({
            "available": False,
            "status": "not_authorized",
            "message": "This admission number is not on the eligible list. Contact the school administration."
        })

    previous = db.session.get(SelfEnrolment, eligibility.current_enrolment_id) if eligibility.current_enrolment_id else None
    if previous and previous.status == "pending":
        return jsonify({"available": False, "status": "pending", "message": "Your request is already under review. Contact the school administration if you need help."})
    if previous and previous.status == "approved":
        return jsonify({"available": False, "status": "registered", "message": "This admission has already been processed. Contact the school administration."})
    if previous and previous.status == "rejected" and previous.resubmission_count >= 1:
        return jsonify({"available": False, "status": "retry_used", "message": "The permitted correction has already been used. Contact the school administration."})

    # Check already registered
    student = Student.query.filter_by(
        school_id=school_id, admission_number=adm_no, is_archived=False
    ).first()
    if student:
        return jsonify({
            "available": False,
            "status": "registered",
            "message": f"Admission '{adm_no}' is already registered ({student.full_name})."
        })

    return jsonify({
        "available": True,
        "status": "resubmit" if previous and previous.status == "rejected" else "available",
        "message": "Your rejected application may be corrected and resubmitted once." if previous and previous.status == "rejected" else f"Admission '{adm_no}' is available."
    })


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: Enrolment Review Queue & Card Generation
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/enrolment/queue")
@login_required
def queue():
    """Admin Queue: Inspect pending submissions, review Card IDs, and generate cards."""
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    status_filter = request.args.get("status", "pending")
    search = request.args.get("search", "").strip()

    query = SelfEnrolment.query.filter_by(school_id=school.id)
    if status_filter in ("pending", "approved", "rejected"):
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.filter(
            (SelfEnrolment.full_name.ilike(f"%{search}%")) |
            (SelfEnrolment.admission_number.ilike(f"%{search}%")) |
            (SelfEnrolment.submission_token.ilike(f"%{search}%"))
        )

    enrolments = query.order_by(SelfEnrolment.submitted_at.desc()).all()
    pending_count = SelfEnrolment.query.filter_by(school_id=school.id, status="pending").count()
    approved_count = SelfEnrolment.query.filter_by(school_id=school.id, status="approved").count()
    rejected_count = SelfEnrolment.query.filter_by(school_id=school.id, status="rejected").count()

    onboard_path = url_for("enrolment.self_enrol", school_code=school.code or school.id)
    onboard_url = build_public_url(onboard_path, school)

    return render_template(
        "enrolment/queue.html",
        current_school=school,
        all_schools=all_schools,
        enrolments=enrolments,
        status_filter=status_filter,
        search=search,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        cbc_classes=CBC_CLASSES,
        old_classes=OLD_844_CLASSES,
        onboard_url=onboard_url
    )


@enrolment_bp.route("/enrolment/<int:enrolment_id>/approve", methods=["POST"])
@login_required
def approve(enrolment_id):
    """Approves a submission, creates/updates Student record, and optionally generates ID card."""
    school = get_current_school()
    enrolment = SelfEnrolment.query.filter_by(
        id=enrolment_id, school_id=school.id
    ).first_or_404()

    if enrolment.status != "pending":
        flash("This submission has already been processed.", "warning")
        return redirect(url_for("enrolment.queue"))

    # Extract allowed overrides from admin form
    full_name    = request.form.get("full_name", enrolment.full_name).strip()
    class_name   = request.form.get("class_name", enrolment.class_name).strip()
    stream_name  = request.form.get("stream_name", enrolment.stream_name or "").strip() or None
    admission_no = request.form.get("admission_number", enrolment.admission_number).strip().upper()
    curriculum   = request.form.get("curriculum_type", enrolment.curriculum_type).strip()

    # Guard admission number collision
    existing = Student.query.filter_by(school_id=school.id, admission_number=admission_no).first()
    if existing:
        flash(
            f"Admission number '{admission_no}' is already assigned to {existing.full_name}. "
            "Please adjust the admission number before approving.",
            "danger"
        )
        return redirect(url_for("enrolment.queue"))

    # Create Student
    student = Student(
        school_id=school.id,
        admission_number=admission_no,
        full_name=full_name,
        curriculum_type=curriculum,
        class_name=class_name,
        stream_name=stream_name,
        academic_year=enrolment.academic_year,
        gender=enrolment.gender,
        dob=enrolment.dob,
        nemis_upi=enrolment.nemis_upi,
        parent_name=enrolment.parent_name,
        parent_phone=enrolment.parent_phone,
        blood_group=enrolment.blood_group,
        house_or_dorm=enrolment.house_or_dorm,
        photo_filename=enrolment.photo_filename,
        photo_cropped_filename=enrolment.photo_filename,
        signature_filename=enrolment.signature_filename,
        card_status="pending",
        enrolment_status="verified",
        pending_card_qr_token=enrolment.card_qr_token,
    )
    db.session.add(student)
    db.session.flush()

    enrolment.status = "approved"
    enrolment.student_id = student.id
    enrolment.reviewed_by_user_id = current_user.id
    enrolment.reviewed_at = datetime.datetime.utcnow()

    # If admin selected "Generate ID Card Now"
    generate_now = request.form.get("generate_now") == "1" or "generate_card" in request.form
    if generate_now:
        base_url = build_public_url("", school).rstrip("/")
        card = CardRenderer.generate_card_for_student(school, student, base_url, qr_token=enrolment.card_qr_token)
        db.session.commit()
        flash(
            f"✅ '{student.full_name}' approved and ID Card #{card.card_number} generated successfully!",
            "success"
        )
        log_audit("APPROVE_AND_GENERATE_ID", f"Approved self-enrolment #{enrolment.id} and generated card {card.card_number}")
        return redirect(url_for("single_id.index", student_id=student.id))

    db.session.commit()
    flash(f"✅ '{student.full_name}' approved and enrolled into the student register.", "success")
    log_audit("APPROVE_ENROLMENT", f"Approved self-enrolment #{enrolment.id} -> student #{student.id}")
    return redirect(url_for("enrolment.queue"))


@enrolment_bp.route("/enrolment/batch-approve", methods=["POST"])
@login_required
def batch_approve():
    """Batch approve multiple submissions and optionally generate all cards at once."""
    school = get_current_school()
    submission_ids = request.form.getlist("enrolment_ids")
    generate_cards = request.form.get("generate_cards") == "1"

    if not submission_ids:
        flash("No submissions selected for batch approval.", "warning")
        return redirect(url_for("enrolment.queue"))

    approved_count = 0
    cards_generated_count = 0
    base_url = build_public_url("", school).rstrip("/")

    for sid in submission_ids:
        enrolment = SelfEnrolment.query.filter_by(id=int(sid), school_id=school.id, status="pending").first()
        if not enrolment:
            continue

        # Skip duplicate admissions
        if Student.query.filter_by(school_id=school.id, admission_number=enrolment.admission_number).first():
            continue

        student = Student(
            school_id=school.id,
            admission_number=enrolment.admission_number,
            full_name=enrolment.full_name,
            curriculum_type=enrolment.curriculum_type,
            class_name=enrolment.class_name,
            stream_name=enrolment.stream_name,
            academic_year=enrolment.academic_year,
            gender=enrolment.gender,
            dob=enrolment.dob,
            nemis_upi=enrolment.nemis_upi,
            parent_name=enrolment.parent_name,
            parent_phone=enrolment.parent_phone,
            blood_group=enrolment.blood_group,
            house_or_dorm=enrolment.house_or_dorm,
            photo_filename=enrolment.photo_filename,
            photo_cropped_filename=enrolment.photo_filename,
            signature_filename=enrolment.signature_filename,
            card_status="pending",
            enrolment_status="verified",
            pending_card_qr_token=enrolment.card_qr_token,
        )
        db.session.add(student)
        db.session.flush()

        enrolment.status = "approved"
        enrolment.student_id = student.id
        enrolment.reviewed_by_user_id = current_user.id
        enrolment.reviewed_at = datetime.datetime.utcnow()
        approved_count += 1

        if generate_cards:
            try:
                CardRenderer.generate_card_for_student(school, student, base_url, qr_token=enrolment.card_qr_token)
                cards_generated_count += 1
            except Exception as e:
                print(f"Failed to generate card for student {student.id}: {e}")

    db.session.commit()
    msg = f"Successfully approved {approved_count} student(s)."
    if generate_cards:
        msg += f" Generated {cards_generated_count} print-ready ID cards."
    flash(msg, "success")
    log_audit("BATCH_APPROVE_ENROLMENT", f"Approved {approved_count} students (Cards generated: {cards_generated_count})")
    return redirect(url_for("enrolment.queue"))


@enrolment_bp.route("/enrolment/<int:enrolment_id>/reject", methods=["POST"])
@login_required
def reject(enrolment_id):
    """Rejects an enrolment submission with reason."""
    school = get_current_school()
    enrolment = SelfEnrolment.query.filter_by(
        id=enrolment_id, school_id=school.id
    ).first_or_404()

    reason = request.form.get("rejection_reason", "").strip() or "Photo/Information did not meet ID production criteria."
    enrolment.status = "rejected"
    enrolment.rejection_reason = reason
    enrolment.reviewed_by_user_id = current_user.id
    enrolment.reviewed_at = datetime.datetime.utcnow()
    db.session.commit()

    flash(f"Submission for '{enrolment.full_name}' was rejected.", "info")
    log_audit("REJECT_ENROLMENT", f"Rejected enrolment #{enrolment_id}: {reason}")
    return redirect(url_for("enrolment.queue"))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: Quick-Add Single Student (with instant card generation option)
# ─────────────────────────────────────────────────────────────────────────────

@enrolment_bp.route("/students/quick-add", methods=["GET", "POST"])
@login_required
def quick_add_student():
    """Streamlined Add Student for front desk or administration staff."""
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    if request.method == "POST":
        full_name       = request.form.get("full_name", "").strip()
        admission_no    = request.form.get("admission_number", "").strip().upper()
        curriculum_type = request.form.get("curriculum_type", "CBC").strip()
        class_name      = request.form.get("class_name", "").strip()
        stream_name     = request.form.get("stream_name", "").strip() or None
        academic_year   = request.form.get("academic_year", school.academic_year).strip()
        gender          = request.form.get("gender", "").strip() or None
        dob             = request.form.get("dob", "").strip() or None
        blood_group     = request.form.get("blood_group", "").strip() or None
        house_or_dorm   = request.form.get("house_or_dorm", "").strip() or None
        nemis_upi       = request.form.get("nemis_upi", "").strip() or None

        errors = []
        if not full_name:
            errors.append("Student full name is required.")
        if not admission_no:
            errors.append("Admission number is required.")
        if not class_name:
            errors.append("Class / Grade is required.")

        if not errors:
            existing = Student.query.filter_by(
                school_id=school.id, admission_number=admission_no
            ).first()
            if existing:
                errors.append(
                    f"Admission number '{admission_no}' is already registered in {school.name}."
                )

        if errors:
            return render_template(
                "enrolment/quick_add.html",
                current_school=school,
                all_schools=all_schools,
                cbc_classes=CBC_CLASSES,
                old_classes=OLD_844_CLASSES,
                blood_groups=BLOOD_GROUPS,
                errors=errors,
                form=request.form
            )

        # Handle Photo (webcam data or upload)
        photo_fn = None
        photo_cropped_data = request.form.get("photo_cropped_data", "").strip()
        webcam_data = request.form.get("webcam_image_data", "").strip()

        if photo_cropped_data and len(photo_cropped_data) > 50:
            photo_fn = save_base64_image(
                photo_cropped_data,
                Config.PHOTOS_DIR,
                prefix=f"photo_{school.id}_{admission_no}_"
            )
        elif webcam_data and len(webcam_data) > 50:
            photo_fn = save_base64_image(
                webcam_data,
                Config.PHOTOS_DIR,
                prefix=f"photo_{school.id}_{admission_no}_"
            )
        elif "photo_file" in request.files:
            pf = request.files["photo_file"]
            if pf and pf.filename:
                photo_fn = save_uploaded_file(
                    pf, Config.PHOTOS_DIR,
                    prefix=f"photo_{school.id}_{admission_no}_"
                )

        student = Student(
            school_id=school.id,
            admission_number=admission_no,
            full_name=full_name,
            curriculum_type=curriculum_type,
            class_name=class_name,
            stream_name=stream_name,
            academic_year=academic_year,
            gender=gender,
            dob=dob,
            blood_group=blood_group,
            house_or_dorm=house_or_dorm,
            nemis_upi=nemis_upi,
            photo_filename=photo_fn,
            photo_cropped_filename=photo_fn,
            card_status="pending",
            enrolment_status="active",
        )
        db.session.add(student)
        db.session.commit()

        flash(f"✅ '{student.full_name}' ({student.admission_number}) added to the student register!", "success")
        log_audit("QUICK_ADD_STUDENT", f"Staff added student {admission_no} via Quick-Add")

        if "generate_now" in request.form:
            base_url = build_public_url("", school).rstrip("/")
            CardRenderer.generate_card_for_student(school, student, base_url)
            return redirect(url_for("single_id.index", student_id=student.id))

        return redirect(url_for("students.index"))

    return render_template(
        "enrolment/quick_add.html",
        current_school=school,
        all_schools=all_schools,
        cbc_classes=CBC_CLASSES,
        old_classes=OLD_844_CLASSES,
        blood_groups=BLOOD_GROUPS,
        errors=[],
        form={}
    )
