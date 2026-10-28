import datetime
import pytest
from app import create_app
from config import TestConfig
from extensions import db
from models import School, Student, CardRecord
from services.qr_service import QRService

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_qr_token_verification(app):
    with app.app_context():
        school = School(name="Maseno School", county="Kisumu")
        db.session.add(school)
        db.session.commit()

        student = Student(
            school_id=school.id,
            admission_number="7788",
            full_name="Barack Obama",
            class_name="Form 4",
            stream_name="North",
            academic_year="2026",
            card_status="active"
        )
        db.session.add(student)
        db.session.commit()

        card = CardRecord(
            school_id=school.id,
            student_id=student.id,
            card_number="MSN-7788",
            qr_token="sample_token_xyz_12345",
            issue_date=datetime.date(2026, 1, 10),
            expiry_date=datetime.date(2029, 12, 31),
            status="active"
        )
        db.session.add(card)
        db.session.commit()

        token_str = QRService.create_token_for_card(school.id, student.id, card.id)
        assert len(token_str) == 32

        # Verify token
        res = QRService.verify_token(token_str)
        assert res["valid"] is True
        assert res["student_name"] == "Barack Obama"
        assert res["school_name"] == "Maseno School"
        assert res["scan_count"] == 1

        # Second scan increments counter
        res2 = QRService.verify_token(token_str)
        assert res2["scan_count"] == 2

        # Invalid token returns valid: False
        invalid_res = QRService.verify_token("invalid_random_token")
        assert invalid_res["valid"] is False
