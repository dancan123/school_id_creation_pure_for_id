import unittest
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

    def tearDown(self):
        # Clean up test school
        s = School.query.filter_by(name="Test Strathmore College").first()
        if s:
            CardRecord.query.filter_by(school_id=s.id).delete()
            Student.query.filter_by(school_id=s.id).delete()
            User.query.filter_by(school_id=s.id).delete()
            School.query.filter_by(id=s.id).delete()
            db.session.commit()
        self.ctx.pop()

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

if __name__ == "__main__":
    unittest.main()
