import datetime
import pytest
from pathlib import Path
from app import create_app
from config import TestConfig, Config
from extensions import db
from models import School, Student, CardRecord
from services.card_renderer import CardRenderer, LANDSCAPE_W, LANDSCAPE_H, generate_barcode_img

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_card_render_dimensions_and_images(app, tmp_path):
    with app.app_context():
        school = School(
            name="Kisumu Boys High School",
            motto="In God We Trust",
            town="Kisumu",
            county="Kisumu",
            primary_color="#1E3A8A",
            secondary_color="#F59E0B"
        )
        db.session.add(school)
        db.session.commit()

        student = Student(
            school_id=school.id,
            admission_number="9876",
            full_name="Amani Otieno",
            class_name="Form 3",
            stream_name="East",
            academic_year="2026"
        )
        db.session.add(student)
        db.session.commit()
        card = CardRecord(
            school_id=school.id,
            student_id=student.id,
            card_number="KBH-9876",
            qr_token="test_token_1234567890abcdef",
            issue_date=datetime.date.today(),
            expiry_date=datetime.date(2029, 12, 31),
            status="active"
        )
        db.session.add(card)
        db.session.commit()

        # Render Front
        front_img = CardRenderer.render_front(school, student, card)
        assert front_img.size == (LANDSCAPE_W, LANDSCAPE_H)
        assert front_img.size == (1011, 638)

        # Render Back
        back_img = CardRenderer.render_back(school, student, card)
        assert back_img.size == (1011, 638)

        # Save images
        f_path = tmp_path / "front.png"
        b_path = tmp_path / "back.png"
        front_img.save(f_path)
        back_img.save(b_path)
        assert f_path.exists()
        assert b_path.exists()

        # Generate Single CR80 PDF
        pdf_path = tmp_path / "test_cr80.pdf"
        CardRenderer.generate_single_cr80_pdf(f_path, b_path, pdf_path)
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000

        # Generate A4 Sheet PDF (with 2 cards)
        a4_pdf_path = tmp_path / "test_a4.pdf"
        CardRenderer.generate_a4_sheet_pdf([(f_path, b_path), (f_path, b_path)], a4_pdf_path)
        assert a4_pdf_path.exists()
        assert a4_pdf_path.stat().st_size > 2000

def test_code128_barcode_is_generated():
    barcode_image = generate_barcode_img("ADM-2026-001")
    assert barcode_image is not None
    assert barcode_image.size == (224, 58)

def test_front_card_does_not_render_blood_group_or_house(app):
    with app.app_context():
        school = School(name="Privacy Test School")
        db.session.add(school)
        db.session.flush()
        student = Student(
            school_id=school.id,
            admission_number="PRIV-001",
            full_name="Privacy Test Student",
            class_name="Grade 8",
            academic_year="2026",
            blood_group="AB-",
            house_or_dorm="HiddenHouse"
        )
        db.session.add(student)
        db.session.flush()
        card = CardRecord(
            school_id=school.id,
            student_id=student.id,
            card_number="ID-PRIV-001",
            qr_token="privacy_test_qr_token_123456",
            issue_date=datetime.date.today(),
            expiry_date=datetime.date(2030, 12, 31),
            status="active"
        )
        db.session.add(card)
        db.session.flush()

        front = CardRenderer.render_front(school, student, card)
        # Assert implementation-level absence as well as successful render; PIL output is rasterized.
        source = Path(CardRenderer.render_front.__code__.co_filename).read_text(encoding="utf-8")
        front_source = source[source.index("def render_front"):source.index("def render_back")]
        assert "blood_group" not in front_source
        assert "house_or_dorm" not in front_source
        assert front.size == (LANDSCAPE_W, LANDSCAPE_H)
