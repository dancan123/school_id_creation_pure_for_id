import pytest
from app import create_app
from config import TestConfig
from extensions import db
from models import School, Student, CardRecord, QRVerificationToken

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

def test_multi_school_creation_and_isolation(app):
    with app.app_context():
        # Create School A
        school_a = School(
            name="Nairobi Academy",
            primary_color="#1E3A8A",
            secondary_color="#F59E0B"
        )
        db.session.add(school_a)
        db.session.commit()

        # Create School B
        school_b = School(
            name="Mombasa High",
            primary_color="#065F46",
            secondary_color="#D97706"
        )
        db.session.add(school_b)
        db.session.commit()

        assert school_a.id != school_b.id
        assert school_a.primary_color == "#1E3A8A"
        assert school_b.primary_color == "#065F46"

        # Both schools can have student with admission number "1001" without collision
        s1 = Student(
            school_id=school_a.id,
            admission_number="1001",
            full_name="Faith Wanjiku",
            class_name="Form 1"
        )
        s2 = Student(
            school_id=school_b.id,
            admission_number="1001",
            full_name="Omar Hassan",
            class_name="Form 1"
        )
        db.session.add_all([s1, s2])
        db.session.commit()

        assert Student.query.filter_by(school_id=school_a.id).count() == 1
        assert Student.query.filter_by(school_id=school_b.id).count() == 1

def test_duplicate_admission_number_within_same_school_rejected(app):
    with app.app_context():
        school = School(name="Nakuru High")
        db.session.add(school)
        db.session.commit()

        s1 = Student(
            school_id=school.id,
            admission_number="ADM-500",
            full_name="John Doe",
            class_name="Form 2"
        )
        db.session.add(s1)
        db.session.commit()

        # Adding same admission number to same school should raise IntegrityError
        s2 = Student(
            school_id=school.id,
            admission_number="ADM-500",
            full_name="Jane Doe",
            class_name="Form 2"
        )
        db.session.add(s2)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
