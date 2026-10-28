import uuid
import datetime
import pytest
from app import create_app
from config import TestConfig, Config
from extensions import db
from models import School, Student, GenerationJob, CardRecord
from services.bulk_generator import BulkGenerator

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_bulk_generation_workflow(app):
    with app.app_context():
        school = School(
            name="Starehe Boys Centre",
            primary_color="#1E3A8A",
            secondary_color="#F59E0B",
            academic_year="2026",
            validity_years=4
        )
        db.session.add(school)
        db.session.commit()

        # Seed 25 synthetic students across Form 1 and Form 2
        students = []
        for i in range(1, 26):
            s = Student(
                school_id=school.id,
                admission_number=f"ST-{1000 + i}",
                full_name=f"Student Number {i}",
                class_name="Form 1" if i <= 15 else "Form 2",
                stream_name="Red" if i % 2 == 0 else "Blue",
                academic_year="2026",
                card_status="pending"
            )
            students.append(s)

        db.session.bulk_save_objects(students)
        db.session.commit()

        assert Student.query.filter_by(school_id=school.id).count() == 25

        # Create Generation Job
        job_id = str(uuid.uuid4())
        job = GenerationJob(
            id=job_id,
            school_id=school.id,
            target_scope="all",
            total_count=25,
            status="queued",
            print_format="cr80_single"
        )
        db.session.add(job)
        db.session.commit()

        # Run Generation
        completed_job = BulkGenerator.run_generation(
            job_id=job_id,
            school_id=school.id,
            student_ids=None,
            print_format="cr80_single"
        )

        assert completed_job.status == "completed"
        assert completed_job.success_count == 25
        assert completed_job.failed_count == 0
        assert completed_job.pdf_filename is not None

        # Verify cards created
        cards = CardRecord.query.filter_by(school_id=school.id).all()
        assert len(cards) == 25
        for card in cards:
            assert card.status == "active"
            assert card.qr_token is not None
            assert card.front_image_filename is not None
            assert card.back_image_filename is not None
            # Verify file exists on disk
            f_p = Config.GENERATED_CARDS_DIR / card.front_image_filename
            b_p = Config.GENERATED_CARDS_DIR / card.back_image_filename
            assert f_p.exists()
            assert b_p.exists()

        # Check compiled PDF file exists
        pdf_path = Config.PDFS_DIR / completed_job.pdf_filename
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 5000
