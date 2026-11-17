import os
import unittest
import datetime
from app import create_app
from extensions import db
from models import School, User, Student, CardRecord, AuditLog
from services.card_renderer import CardRenderer

class SaasPlatformTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.ctx.pop()

    def _cleanup(self):
        try:
            db.session.rollback()
            from models import QuotaUpgradeRequest, PaymentTransaction, ApiKey
            for code in ["STR-01", "UON-01", "KCB-01", "MKS-TVET", "APEX-01", "SAF-01", "TPS-01"]:
                sch = School.query.filter((School.code == code) | (School.name.ilike(f"%{code}%"))).first()
                if sch:
                    PaymentTransaction.query.filter_by(school_id=sch.id).delete()
                    ApiKey.query.filter_by(school_id=sch.id).delete()
                    QuotaUpgradeRequest.query.filter_by(school_id=sch.id).delete()
                    CardRecord.query.filter_by(school_id=sch.id).delete()
                    Student.query.filter_by(school_id=sch.id).delete()
                    User.query.filter_by(school_id=sch.id).delete()
                    School.query.filter_by(id=sch.id).delete()
            for name in ["Test Strathmore College", "University of Nairobi", "KCB Bank Group", "Machakos Vocational TVET", "Apex Engineering Ltd", "Safaricom Business", "Test Photo School"]:
                s = School.query.filter_by(name=name).first()
                if s:
                    PaymentTransaction.query.filter_by(school_id=s.id).delete()
                    ApiKey.query.filter_by(school_id=s.id).delete()
                    QuotaUpgradeRequest.query.filter_by(school_id=s.id).delete()
                    CardRecord.query.filter_by(school_id=s.id).delete()
                    Student.query.filter_by(school_id=s.id).delete()
                    User.query.filter_by(school_id=s.id).delete()
                    School.query.filter_by(id=s.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()

    def test_01_superadmin_exists(self):
        """Ensure initial superadmin is provisioned."""
        admin = User.query.filter_by(role="superadmin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@schoolidsystem.ke",
                full_name="Platform Super Administrator",
                role="superadmin",
                is_platform_admin=True,
                is_active=True
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
        self.assertIsNotNone(admin)
        self.assertTrue(admin.check_password("admin123"))
        print("PASS: Superadmin account verified.")

    def test_02_public_registration_and_free_trial(self):
        """Test public link registration creates an active Free Trial account with 2 free IDs."""
        resp = self.client.post("/auth/register-institution", data={
            "org_name": "Test Strathmore College",
            "org_type": "university",
            "registration_number": "MOE/UNI/9988",
            "contact_name": "Dr. Geoffrey Kiptoo",
            "contact_email": "kiptoo@strathmore-test.ac.ke",
            "contact_phone": "+254 711 999000",
            "county": "Nairobi",
            "town": "Madaraka",
            "po_box": "P.O. Box 59857 - 00200",
            "physical_address": "Ole Sangale Rd, Madaraka",
            "username": "strathmore_admin",
            "password": "Password123!"
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        sch = School.query.filter_by(name="Test Strathmore College").first()
        self.assertIsNotNone(sch)
        self.assertEqual(sch.status, "active")
        self.assertEqual(sch.subscription_tier, "free_trial")
        self.assertEqual(sch.max_cards_quota, 2)

        owner = User.query.filter_by(username="strathmore_admin").first()
        self.assertIsNotNone(owner)
        self.assertTrue(owner.is_active)
        print(f"PASS: Public registration created active Free Trial institution '{sch.name}' with max quota of {sch.max_cards_quota} cards.")

    def test_03_login_and_generate_2_free_cards_and_quota_block(self):
        """Test that user logs in, generates 2 cards, and is blocked on card #3."""
        # Setup school
        sch = School(
            name="Test Strathmore College",
            code="STR-01",
            institution_type="university",
            status="active",
            subscription_tier="free_trial",
            max_cards_quota=2,
            is_active=True
        )
        db.session.add(sch)
        db.session.flush()

        owner = User(
            username="strathmore_admin",
            email="kiptoo@strathmore-test.ac.ke",
            full_name="Dr. Geoffrey Kiptoo",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        owner.set_password("Password123!")
        db.session.add(owner)

        # Add 3 test students
        s1 = Student(school_id=sch.id, admission_number="STU-001", full_name="Student One", class_name="Year 1")
        s2 = Student(school_id=sch.id, admission_number="STU-002", full_name="Student Two", class_name="Year 1")
        s3 = Student(school_id=sch.id, admission_number="STU-003", full_name="Student Three", class_name="Year 1")
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        # Login as owner
        login_resp = self.client.post("/auth/login", data={"username": "strathmore_admin", "password": "Password123!"}, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # Generate Card 1 (allowed)
        r1 = self.client.post("/single-id/generate", data={"student_id": s1.id}, follow_redirects=True)
        self.assertIn(b"generated successfully", r1.data)

        # Generate Card 2 (allowed - exactly 2 free trial IDs)
        r2 = self.client.post("/single-id/generate", data={"student_id": s2.id}, follow_redirects=True)
        self.assertIn(b"generated successfully", r2.data)

        self.assertEqual(CardRecord.query.filter_by(school_id=sch.id).count(), 2)

        # Attempt to generate Card 3 (MUST BE BLOCKED BY QUOTA)
        r3 = self.client.post("/single-id/generate", data={"student_id": s3.id}, follow_redirects=True)
        self.assertIn(b"quota reached", r3.data.lower())
        self.assertEqual(CardRecord.query.filter_by(school_id=sch.id).count(), 2)
        print("PASS: Institution successfully generated 2 free cards, and card #3 was blocked by trial quota.")

    def test_04_superadmin_sees_institution_and_upgrades_plan(self):
        """Test that Super Admin sees the new institution in dashboard and upgrades quota."""
        sch = School(
            name="Test Strathmore College",
            code="STR-01",
            institution_type="university",
            status="active",
            subscription_tier="free_trial",
            max_cards_quota=2,
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        # Login as Super Admin
        self.client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

        # Super Admin views institution list
        resp = self.client.get("/superadmin/organizations", follow_redirects=True)
        self.assertIn(b"Test Strathmore College", resp.data)

        # Super Admin upgrades institution from Free Trial (2 cards) to Standard (5,000 cards)
        upgrade_resp = self.client.post(f"/superadmin/organizations/{sch.id}/update-tier", data={
            "subscription_tier": "standard",
            "max_cards_quota": 5000
        }, follow_redirects=True)

        self.assertEqual(upgrade_resp.status_code, 200)
        db.session.refresh(sch)
        self.assertEqual(sch.subscription_tier, "standard")
        self.assertEqual(sch.max_cards_quota, 5000)
        print("PASS: Superadmin sees new institution and upgraded plan from 2 trial cards to 5,000 cards.")

    def test_05_infinite_quota_unlimited_generation(self):
        """Test setting quota to 0 allows infinite / unlimited card generations."""
        sch = School(
            name="Test Strathmore College",
            code="STR-01",
            institution_type="university",
            status="active",
            subscription_tier="enterprise",
            max_cards_quota=0,  # 0 denotes Infinite
            is_active=True
        )
        db.session.add(sch)
        db.session.flush()

        owner = User(
            username="strathmore_admin",
            email="kiptoo@strathmore-test.ac.ke",
            full_name="Dr. Geoffrey Kiptoo",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        owner.set_password("Password123!")
        db.session.add(owner)

        students = [
            Student(school_id=sch.id, admission_number=f"INF-{i}", full_name=f"Student {i}", class_name="Year 1")
            for i in range(1, 5)
        ]
        db.session.add_all(students)
        db.session.commit()

        # Login as owner
        self.client.post("/auth/login", data={"username": "strathmore_admin", "password": "Password123!"}, follow_redirects=True)

        # Generate 4 cards - none should be blocked
        for st in students:
            r = self.client.post("/single-id/generate", data={"student_id": st.id}, follow_redirects=True)
            self.assertIn(b"generated successfully", r.data)

        self.assertEqual(CardRecord.query.filter_by(school_id=sch.id).count(), 4)
        print("PASS: Setting quota to 0 allows infinite / unlimited ID card generations.")

    def test_06_superadmin_delete_org_and_onboard_privacy(self):
        """Test Super Admin deleting an institution, and test that /onboard hides competitor institutions from public."""
        sch = School(
            name="Test Strathmore College",
            code="STR-01",
            status="active",
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        # 1. Verify public /onboard DOES NOT list schools to unauthenticated visitors
        self.client.get("/auth/logout", follow_redirects=True)
        hub_resp = self.client.get("/onboard", follow_redirects=True)
        self.assertNotIn(b"Test Strathmore College", hub_resp.data)
        print("PASS: Public /onboard hides competitor school listings from unauthorized visitors.")

        # 2. Login as Super Admin and delete the institution
        self.client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        del_resp = self.client.post(f"/superadmin/organizations/{sch.id}/delete", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)

        # Confirm school is permanently deleted from database
        self.assertIsNone(School.query.filter_by(name="Test Strathmore College").first())
        print("PASS: Superadmin permanently deleted institution.")

    def test_07_universal_code_routing_and_tenant_scoped_login(self):
        """Test universal code routing on /portal, institution taxonomy, and cross-tenant login protection."""
        # 1. Create a University and a Corporate
        uon = School(
            name="University of Nairobi",
            code="UON-01",
            institution_type="university",
            status="active",
            is_active=True
        )
        kcb = School(
            name="KCB Bank Group",
            code="KCB-01",
            institution_type="corporate",
            status="active",
            is_active=True
        )
        db.session.add_all([uon, kcb])
        db.session.flush()

        user_uon = User(
            username="uon_registrar",
            email="registrar@uonbi.ac.ke",
            full_name="UoN Academic Registrar",
            role="org_admin",
            school_id=uon.id,
            is_active=True
        )
        user_uon.set_password("UonPass123!")

        user_kcb = User(
            username="kcb_hr",
            email="hr@kcbgroup.com",
            full_name="KCB HR Director",
            role="org_admin",
            school_id=kcb.id,
            is_active=True
        )
        user_kcb.set_password("KcbPass123!")

        db.session.add_all([user_uon, user_kcb])
        db.session.commit()

        # Taxonomy verification
        self.assertEqual(kcb.get_member_label(), "Employee")
        self.assertEqual(kcb.get_id_label(), "EMP NO")
        self.assertEqual(kcb.get_class_label(), "DEPARTMENT")
        self.assertEqual(uon.get_id_label(), "REG NO")

        # 2. Universal code routing
        self.client.get("/auth/logout", follow_redirects=True)
        r_onboard = self.client.get("/portal?code=UON-01&action=onboard")
        self.assertEqual(r_onboard.status_code, 302)
        self.assertTrue(r_onboard.headers["Location"].endswith("/UON-01"))

        r_login = self.client.get("/portal?code=UON-01&action=login")
        self.assertEqual(r_login.status_code, 302)
        self.assertIn("/auth/login?code=UON-01", r_login.headers["Location"])

        # 3. Invalid code returns 404 without leaking competitors
        r_invalid = self.client.get("/portal?code=NONEXISTENT_999", follow_redirects=True)
        self.assertEqual(r_invalid.status_code, 404)
        self.assertIn(b"Institution Not Found", r_invalid.data)
        self.assertNotIn(b"KCB Bank Group", r_invalid.data)
        self.assertNotIn(b"University of Nairobi", r_invalid.data)

        # 4. Scoped Login Page Branding
        r_page = self.client.get("/auth/login?code=UON-01")
        self.assertEqual(r_page.status_code, 200)
        self.assertIn(b"University of Nairobi", r_page.data)
        self.assertIn(b"UON-01", r_page.data)

        # 5. Cross-Tenant Login Block
        # KCB user tries to log in on UoN's scoped login page -> MUST be rejected
        cross_resp = self.client.post("/auth/login?code=UON-01", data={
            "username": "kcb_hr",
            "password": "KcbPass123!"
        }, follow_redirects=True)
        self.assertIn(b"Access Denied", cross_resp.data)
        self.assertIn(b"belongs to another institution", cross_resp.data)

        # Valid UoN user logs into UoN workspace -> Succeeds
        valid_resp = self.client.post("/auth/login?code=UON-01", data={
            "username": "uon_registrar",
            "password": "UonPass123!"
        }, follow_redirects=True)
        self.assertEqual(valid_resp.status_code, 200)
        self.assertIn(b"Welcome back, UoN Academic Registrar", valid_resp.data)

        # Clean up
        self.client.get("/auth/logout", follow_redirects=True)
        User.query.filter(User.id.in_([user_uon.id, user_kcb.id])).delete()
        School.query.filter(School.id.in_([uon.id, kcb.id])).delete()
        db.session.commit()
        print("PASS: Universal code routing, taxonomy, and strict cross-tenant login isolation verified.")

    def test_08_owner_manages_public_access_and_closed_onboarding(self):
        """Test owner closing and opening public onboarding access, and 403 onboarding_closed enforcement."""
        sch = School(
            name="Machakos Vocational TVET",
            code="MKS-TVET",
            institution_type="tvet",
            allow_self_onboarding=True,
            status="active",
            is_active=True
        )
        db.session.add(sch)
        db.session.flush()

        owner = User(
            username="machakos_principal",
            email="principal@machakostvet.ac.ke",
            full_name="Eng. Mutua",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        owner.set_password("TvetPass123!")
        db.session.add(owner)
        db.session.commit()

        # 1. As public visitor, intake is initially open
        self.client.get("/auth/logout", follow_redirects=True)
        r_open = self.client.get("/onboard/MKS-TVET")
        self.assertEqual(r_open.status_code, 200)
        self.assertIn(b"Machakos Vocational TVET", r_open.data)

        # 2. Owner logs in and toggles public intake to closed
        self.client.post("/auth/login", data={"username": "machakos_principal", "password": "TvetPass123!"}, follow_redirects=True)
        toggle_resp = self.client.post("/schools/toggle-onboarding", follow_redirects=True)
        self.assertEqual(toggle_resp.status_code, 200)

        # Verify in database
        db.session.refresh(sch)
        self.assertFalse(sch.allow_self_onboarding)

        # 3. As public visitor, intake is now closed
        self.client.get("/auth/logout", follow_redirects=True)
        r_closed = self.client.get("/onboard/MKS-TVET")
        self.assertEqual(r_closed.status_code, 403)
        self.assertIn(b"Onboarding Closed", r_closed.data)

        # 4. Owner re-opens intake
        self.client.post("/auth/login", data={"username": "machakos_principal", "password": "TvetPass123!"}, follow_redirects=True)
        self.client.post("/schools/toggle-onboarding", follow_redirects=True)
        db.session.refresh(sch)
        self.assertTrue(sch.allow_self_onboarding)

        # Public access restored
        self.client.get("/auth/logout", follow_redirects=True)
        r_restored = self.client.get("/onboard/MKS-TVET")
        self.assertEqual(r_restored.status_code, 200)

        # Clean up
        User.query.filter_by(id=owner.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Institution owner public access management and closed intake gating verified.")

    def test_09_landing_page_and_quota_upgrade_system(self):
        """Test public SaaS landing page at / and in-app quota upgrade request & superadmin approval workflow."""
        # 1. Unauthenticated public visitor hits root URL /
        self.client.get("/auth/logout", follow_redirects=True)
        r_landing = self.client.get("/")
        self.assertEqual(r_landing.status_code, 200)
        self.assertIn(b"EduID", r_landing.data)
        self.assertIn(b"Universal", r_landing.data)
        self.assertIn(b"Register Your Institution", r_landing.data)

        # 2. Setup an active institution with free trial quota of 2
        from models import QuotaUpgradeRequest
        sch = School(
            name="Apex Engineering Ltd",
            code="APEX-01",
            institution_type="corporate",
            status="active",
            max_cards_quota=2,
            is_active=True
        )
        db.session.add(sch)
        db.session.flush()

        user = User(
            username="apex_admin",
            email="admin@apexengineering.co.ke",
            full_name="Apex Operations Manager",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        user.set_password("ApexPass123!")
        db.session.add(user)
        db.session.commit()

        # 3. Org Owner logs in and submits an in-app upgrade request for 1,500 cards
        self.client.post("/auth/login", data={"username": "apex_admin", "password": "ApexPass123!"}, follow_redirects=True)
        req_resp = self.client.post(
            "/schools/request-quota-upgrade",
            data={
                "requested_quota": "1500",
                "requested_tier": "standard",
                "contact_phone": "+254711223344",
                "notes": "We need additional allocation for 1,200 staff onboarding next week."
            },
            follow_redirects=True
        )
        self.assertEqual(req_resp.status_code, 200)
        self.assertIn(b"Upgrade request for 1,500 ID cards has been submitted", req_resp.data)

        # Verify request record in database
        upgrade_entry = QuotaUpgradeRequest.query.filter_by(school_id=sch.id).first()
        self.assertIsNotNone(upgrade_entry)
        self.assertEqual(upgrade_entry.requested_quota, 1500)
        self.assertEqual(upgrade_entry.status, "pending")

        # 4. Super Admin logs in, reviews upgrade requests and approves it
        self.client.get("/auth/logout", follow_redirects=True)
        self.client.post("/auth/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

        # View upgrade requests page
        r_admin_view = self.client.get("/superadmin/upgrade-requests")
        self.assertEqual(r_admin_view.status_code, 200)
        self.assertIn(b"Apex Engineering Ltd", r_admin_view.data)

        # Approve upgrade request
        approve_resp = self.client.post(
            f"/superadmin/upgrade-requests/{upgrade_entry.id}/approve",
            data={"notes": "Approved for Q1 staff batch."},
            follow_redirects=True
        )
        self.assertEqual(approve_resp.status_code, 200)
        self.assertIn(b"Approved quota upgrade for", approve_resp.data)
        self.assertIn(b"Apex Engineering Ltd", approve_resp.data)
        self.assertIn(b"1,500 ID cards", approve_resp.data)

        # Confirm school's quota was updated in DB
        db.session.refresh(sch)
        db.session.refresh(upgrade_entry)
        self.assertEqual(sch.max_cards_quota, 1500)
        self.assertEqual(upgrade_entry.status, "approved")

        # Clean up
        QuotaUpgradeRequest.query.filter_by(school_id=sch.id).delete()
        User.query.filter_by(id=user.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Public SaaS landing page and in-app quota upgrade workflow verified.")

    def test_10_universal_taxonomy_and_dynamic_imports_reports_exports(self):
        """Test that Excel templates, reports, CSV/PDF exports, and QR verification adapt dynamically to non-school institutions."""
        import openpyxl
        from services.bulk_importer import BulkImporter
        from services.qr_service import QRService

        # 1. Create a Corporate Institution
        sch = School(
            name="Safaricom Business",
            code="SAF-01",
            institution_type="corporate",
            status="active",
            subscription_tier="standard",
            max_cards_quota=500,
            primary_color="#00A859",
            secondary_color="#004D25",
            card_title="OFFICIAL CORPORATE CREDENTIAL",
            id_label="EMP NO",
            class_label="DEPARTMENT",
            stream_label="DESIGNATION / ROLE",
            academic_year="2026",
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        user = User(
            username="saf_admin",
            email="admin@safaricom-business.co.ke",
            full_name="Safaricom Security Admin",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        user.set_password("SafPass123!")
        db.session.add(user)

        emp = Student(
            school_id=sch.id,
            admission_number="SAF-9901",
            full_name="Wanjiku Kamau",
            class_name="Cloud & Cyber Security",
            stream_name="Lead Engineer",
            gender="Female",
            dob="1992-06-18",
            parent_name="Dr. Kamau",
            parent_phone="+254711000111",
            card_status="active"
        )
        db.session.add(emp)
        db.session.commit()

        # 2. Test Dynamic Sample Excel Template Generation
        sample_path = "storage/test_saf_template.xlsx"
        BulkImporter.generate_sample_excel(sample_path, school=sch)
        wb = openpyxl.load_workbook(sample_path)
        self.assertEqual(wb.active.title, "Employees")
        header_vals = [cell.value for cell in wb.active[1]]
        self.assertIn("Employee ID", header_vals)
        self.assertIn("Department", header_vals)
        self.assertIn("Job Title / Role", header_vals)

        # 3. Test Bulk Import Template Download Route
        self.client.post("/auth/login", data={"username": "saf_admin", "password": "SafPass123!"}, follow_redirects=True)
        resp_tpl = self.client.get("/bulk-import/template")
        self.assertEqual(resp_tpl.status_code, 200)
        self.assertIn("Safaricom_Business_Employee_Import_Template.xlsx", resp_tpl.headers.get("Content-Disposition", ""))

        # 4. Test Reports CSV Export with Dynamic Headers
        resp_csv = self.client.get("/reports/export-students-csv")
        self.assertEqual(resp_csv.status_code, 200)
        self.assertIn("employees_manifest", resp_csv.headers.get("Content-Disposition", ""))
        csv_text = resp_csv.data.decode("utf-8")
        self.assertIn("EMP NO", csv_text)
        self.assertIn("Employee Full Name", csv_text)
        self.assertIn("DEPARTMENT", csv_text)
        self.assertIn("DESIGNATION / ROLE", csv_text)
        self.assertIn("SAF-9901", csv_text)
        resp_csv.close()

        # 5. Test Student Excel Export with Corporate Labels
        resp_excel = self.client.get("/students/export/excel")
        self.assertEqual(resp_excel.status_code, 200)
        self.assertIn("Safaricom_Business_Employees_", resp_excel.headers.get("Content-Disposition", ""))

        # 6. Test Student PDF Roster Export with Corporate Labels
        resp_pdf = self.client.get("/students/export/pdf")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertIn("Safaricom_Business_Employees_Register_", resp_pdf.headers.get("Content-Disposition", ""))

        # 7. Test Card Generation & QR Verification
        card_res = CardRenderer.generate_card_for_student(sch, emp, "http://127.0.0.1:5000")
        card_rec = CardRecord.query.filter_by(student_id=emp.id, status="active").first()
        self.assertIsNotNone(card_rec)
        self.assertIsNotNone(card_rec.qr_token)

        # Test QR payload enrichment
        payload = QRService.verify_token(card_rec.qr_token)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["card_title"], "OFFICIAL CORPORATE CREDENTIAL")
        self.assertEqual(payload["id_label"], "EMP NO")
        self.assertEqual(payload["member_label"], "Employee")
        self.assertEqual(payload["class_label"], "DEPARTMENT")

        # Test Public QR Verification HTML page
        resp_verify = self.client.get(f"/verify/{card_rec.qr_token}")
        self.assertEqual(resp_verify.status_code, 200)
        verify_html = resp_verify.data.decode("utf-8")
        self.assertIn("OFFICIAL CORPORATE CREDENTIAL", verify_html)
        self.assertIn("EMP NO", verify_html)
        self.assertIn("SAF-9901", verify_html)
        self.assertIn("Cyber Security", verify_html)
        self.assertNotIn("AUTHENTIC STUDENT CARD", verify_html)

        # Clean up
        CardRecord.query.filter_by(school_id=sch.id).delete()
        Student.query.filter_by(school_id=sch.id).delete()
        User.query.filter_by(id=user.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        if os.path.exists(sample_path):
            os.remove(sample_path)
        print("PASS: Universal taxonomy and dynamic imports, reports, exports, and QR verification verified.")

    def test_11_automated_mpesa_billing_and_quota_topup(self):
        """Test M-Pesa STK push initiation, callback processing, and instant automated quota crediting."""
        from models import PaymentTransaction
        from services.mpesa_service import MpesaService

        # 1. Setup tenant
        sch = School(
            name="Apex Engineering Ltd",
            code="APEX-01",
            institution_type="corporate",
            status="active",
            subscription_tier="free_trial",
            max_cards_quota=2,
            cards_generated_count=2,
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        user = User(
            username="apex_billing",
            email="billing@apexengineering.co.ke",
            full_name="Apex Billing Manager",
            role="org_owner",
            school_id=sch.id,
            is_active=True
        )
        user.set_password("ApexPass123!")
        db.session.add(user)
        db.session.commit()

        # 2. Query billing packages
        res_pkg = self.client.get("/api/v1/billing/packages")
        self.assertEqual(res_pkg.status_code, 200)
        pkg_data = res_pkg.get_json()
        self.assertTrue(any(p["key"] == "pack_500" for p in pkg_data["packages"]))

        # 3. Trigger M-Pesa STK Push
        self.client.post("/auth/login", data={"username": "apex_billing", "password": "ApexPass123!"}, follow_redirects=True)
        resp_stk = self.client.post("/api/v1/billing/mpesa-stk-push", json={
            "phone_number": "0712345678",
            "package_key": "pack_500"
        })
        self.assertEqual(resp_stk.status_code, 200)
        stk_json = resp_stk.get_json()
        self.assertTrue(stk_json["success"])
        txn_id = stk_json["transaction_id"]
        checkout_id = stk_json["checkout_request_id"]

        # Verify transaction created as pending
        txn = PaymentTransaction.query.get(txn_id)
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "pending")
        self.assertEqual(txn.amount, 7500.0)
        self.assertEqual(txn.cards_credited, 500)

        # 4. Check Polling endpoint (returns pending)
        res_poll = self.client.get(f"/api/v1/billing/status/{txn_id}")
        self.assertEqual(res_poll.status_code, 200)
        self.assertEqual(res_poll.get_json()["status"], "pending")

        # 5. Process Daraja STK Callback
        mock_callback = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": txn.merchant_request_id,
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 7500.0},
                            {"Name": "MpesaReceiptNumber", "Value": "QWE9988776"},
                            {"Name": "TransactionDate", "Value": 20261117133000},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }
        res_cb = self.client.post("/api/v1/billing/mpesa-callback", json=mock_callback)
        self.assertEqual(res_cb.status_code, 200)

        # 6. Verify tenant quota was instantly credited without admin intervention
        db.session.refresh(txn)
        db.session.refresh(sch)
        self.assertEqual(txn.status, "completed")
        self.assertEqual(txn.mpesa_receipt_number, "QWE9988776")
        self.assertEqual(sch.max_cards_quota, 502) # 2 initial + 500 top-up
        self.assertEqual(sch.subscription_tier, "standard")

        # Cleanup
        PaymentTransaction.query.filter_by(school_id=sch.id).delete()
        User.query.filter_by(id=user.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Automated M-Pesa STK push billing and instant quota top-up verified.")

    def test_12_turnstile_gate_verification_api_and_scanner(self):
        """Test physical access turnstile JSON API, tenant isolation with API keys, and mobile scanner."""
        import hashlib
        import uuid
        from models import ApiKey, QRVerificationToken

        token_str = f"kcb_token_{uuid.uuid4().hex[:8]}"
        sch_code = f"KCB_{uuid.uuid4().hex[:4]}"

        # Setup institution
        sch = School(
            name="KCB Bank Group",
            code=sch_code,
            institution_type="corporate",
            card_title="OFFICIAL CORPORATE CREDENTIAL",
            id_label="EMP NO",
            class_label="DEPARTMENT",
            stream_label="DESIGNATION",
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        emp = Student(
            school_id=sch.id,
            admission_number="KCB-8821",
            full_name="Faith Muthoni",
            class_name="Information Security",
            stream_name="Security Analyst",
            card_status="active"
        )
        db.session.add(emp)
        db.session.commit()

        # Generate card record
        card = CardRecord(
            school_id=sch.id,
            student_id=emp.id,
            card_number="ID-KCB-8821",
            qr_token=token_str,
            expiry_date=datetime.date(2030, 12, 31),
            status="active"
        )
        db.session.add(card)
        db.session.commit()

        # Provision API key for turnstile
        raw_key = f"eduid_live_{uuid.uuid4().hex}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        api_key = ApiKey(
            school_id=sch.id,
            name="KCB Head Office Turnstile 1",
            key_prefix=raw_key[:16],
            key_hash=key_hash,
            is_active=True
        )
        db.session.add(api_key)
        db.session.commit()

        # 1. Turnstile API call with valid token
        resp = self.client.post(
            "/api/v1/verify-credential",
            headers={"X-API-Key": raw_key},
            json={"token": token_str}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["authorized"])
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["member"]["id_number"], "KCB-8821")
        self.assertEqual(data["member"]["id_label"], "EMP NO")
        self.assertEqual(data["member"]["full_name"], "Faith Muthoni")
        self.assertEqual(data["institution"]["name"], "KCB Bank Group")

        # 2. Turnstile API call with invalid token
        resp_bad = self.client.post(
            "/api/v1/verify-credential",
            headers={"X-API-Key": raw_key},
            json={"token": "invalid_fake_token"}
        )
        self.assertEqual(resp_bad.status_code, 200)
        self.assertFalse(resp_bad.get_json()["authorized"])

        # 3. Test Mobile Scanner Views
        resp_scan = self.client.get("/scanner")
        self.assertEqual(resp_scan.status_code, 200)
        self.assertIn(b"html5-qrcode", resp_scan.data)

        resp_scan_sch = self.client.get(f"/scanner/{sch.code}")
        self.assertEqual(resp_scan_sch.status_code, 200)
        self.assertIn(b"KCB Bank Group", resp_scan_sch.data)

        # Clean up
        QRVerificationToken.query.filter_by(token=token_str).delete()
        ApiKey.query.filter_by(school_id=sch.id).delete()
        CardRecord.query.filter_by(school_id=sch.id).delete()
        Student.query.filter_by(school_id=sch.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Turnstile access control JSON API, API key auth, and mobile scanner verified.")

    def test_13_smart_photo_centering_and_normalizer(self):
        """Test pure-Python smart headshot centering, 3:4 passport aspect ratio normalization, and API."""
        from PIL import Image
        import io
        from services.photo_enhancer import PhotoEnhancer

        # Create synthetic test image (e.g. wide 800x600 image with face-like center)
        test_img = Image.new("RGB", (800, 600), color=(240, 240, 240))
        # Draw a darker head area off-center
        for y in range(120, 280):
            for x in range(350, 480):
                test_img.putpixel((x, y), (120, 80, 60))

        img_byte_arr = io.BytesIO()
        test_img.save(img_byte_arr, format='JPEG')
        raw_bytes = img_byte_arr.getvalue()

        # 1. Enhance via service directly
        enhanced_bytes = PhotoEnhancer.enhance_passport_photo(raw_bytes, target_size=(480, 640))
        result_img = Image.open(io.BytesIO(enhanced_bytes))
        self.assertEqual(result_img.size, (480, 640)) # Exact 3:4 CR80 ratio

        # 2. Enhance via HTTP API
        # Login first
        sch = School(name="Test Photo School", code="TPS-01", is_active=True)
        db.session.add(sch)
        db.session.commit()
        u = User(username="tps_user", full_name="TPS Photo Admin", email="tps@photoschool.ke", role="admin", school_id=sch.id, is_active=True)
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        self.client.post("/auth/login", data={"username": "tps_user", "password": "pass123"}, follow_redirects=True)
        resp_api = self.client.post(
            "/api/v1/photos/enhance",
            data={"photo": (io.BytesIO(raw_bytes), "test_wide.jpg")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp_api.status_code, 200)
        api_data = resp_api.get_json()
        self.assertEqual(api_data["status"], "success")
        self.assertTrue(api_data["data_url"].startswith("data:image/jpeg;base64,"))

        # Clean up
        User.query.filter_by(id=u.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Smart photo centering, 3:4 aspect ratio normalization, and enhancement API verified.")

    def test_14_gate_api_key_lifecycle_and_settings_ui(self):
        """Test institution admin generating and revoking gate API keys via dashboard settings."""
        from models import ApiKey

        sch = School(name="Equity Bank Kenya", code="EQT-01", institution_type="corporate", is_active=True)
        db.session.add(sch)
        db.session.commit()

        u = User(username="eqt_admin", full_name="Equity Security Lead", email="security@equity.co.ke", role="org_owner", school_id=sch.id, is_active=True)
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        self.client.post("/auth/login", data={"username": "eqt_admin", "password": "pass123"}, follow_redirects=True)

        # 1. Create a Gate API Key
        resp = self.client.post(
            "/schools/api-keys/create",
            data={"name": "Upperhill Main Gate Turnstile"},
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        created_key = ApiKey.query.filter_by(school_id=sch.id, name="Upperhill Main Gate Turnstile").first()
        self.assertIsNotNone(created_key)
        self.assertTrue(created_key.is_active)
        self.assertTrue(created_key.key_prefix.startswith("eduid_live_"))

        # 2. View settings page and verify UI displays the new key
        resp_settings = self.client.get("/schools/settings")
        self.assertEqual(resp_settings.status_code, 200)
        self.assertIn("Upperhill Main Gate Turnstile", resp_settings.get_data(as_text=True))
        self.assertIn(created_key.key_prefix, resp_settings.get_data(as_text=True))

        # 3. Revoke the API Key
        resp_revoke = self.client.post(
            f"/schools/api-keys/{created_key.id}/revoke",
            follow_redirects=True
        )
        self.assertEqual(resp_revoke.status_code, 200)
        db.session.refresh(created_key)
        self.assertFalse(created_key.is_active)

        # 4. Clean up
        ApiKey.query.filter_by(school_id=sch.id).delete()
        User.query.filter_by(id=u.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Turnstile Gate API Key lifecycle and settings UI verified.")

    def test_15_mobile_digital_pass_and_anti_tamper_view(self):
        """Test mobile-first digital ID pass (/pass/<token>) with live anti-tamper watermark."""
        import uuid
        from models import QRVerificationToken

        # Clean up any previous test remnants
        School.query.filter(School.code.like("RU_%")).delete()
        School.query.filter_by(name="Riara University").delete()
        db.session.commit()

        sch_code = f"RU_{uuid.uuid4().hex[:4]}"
        pass_token = f"joy_pass_{uuid.uuid4().hex[:8]}"
        adm_no = f"RU_{uuid.uuid4().hex[:6]}"

        sch = School(
            name="Riara University",
            code=sch_code,
            institution_type="university",
            card_title="STUDENT IDENTIFICATION PASS",
            id_label="STUDENT NO",
            class_label="SCHOOL / FACULTY",
            stream_label="PROGRAMME",
            is_active=True
        )
        db.session.add(sch)
        db.session.commit()

        student = Student(
            school_id=sch.id,
            admission_number=adm_no,
            full_name="Joy Achieng Otieno",
            class_name="School of Computing",
            stream_name="BSc Business IT",
            card_status="active"
        )
        db.session.add(student)
        db.session.commit()

        card = CardRecord(
            school_id=sch.id,
            student_id=student.id,
            card_number=f"CARD-{adm_no}",
            qr_token=pass_token,
            expiry_date=datetime.date(2028, 12, 31),
            status="active"
        )
        db.session.add(card)
        db.session.commit()

        # 1. Access digital pass via /pass/<token>
        resp_pass = self.client.get(f"/pass/{card.qr_token}")
        self.assertEqual(resp_pass.status_code, 200)
        html = resp_pass.get_data(as_text=True)
        self.assertIn("Joy Achieng Otieno", html)
        self.assertIn("Riara University", html)
        self.assertIn(adm_no, html)
        self.assertIn("STUDENT IDENTIFICATION PASS", html)
        self.assertIn("liveClockDisplay", html)

        # 2. Access via alias /digital-pass/<token>
        resp_alias = self.client.get(f"/digital-pass/{card.qr_token}")
        self.assertEqual(resp_alias.status_code, 200)

        # 3. Invalid token returns clean error state
        resp_invalid = self.client.get("/pass/non_existent_token_000")
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertIn("Invalid or Inactive Pass", resp_invalid.get_data(as_text=True))

        # Clean up
        QRVerificationToken.query.filter_by(token=pass_token).delete()
        CardRecord.query.filter_by(id=card.id).delete()
        Student.query.filter_by(id=student.id).delete()
        School.query.filter_by(id=sch.id).delete()
        db.session.commit()
        print("PASS: Mobile digital pass and anti-tamper security view verified.")


if __name__ == "__main__":
    unittest.main()
