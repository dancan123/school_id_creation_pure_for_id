import pytest
import zipfile
from PIL import Image
from app import create_app
from config import TestConfig
from extensions import db
from models import School, Student
from services.bulk_importer import BulkImporter

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_excel_generation_and_import(app, tmp_path):
    with app.app_context():
        school = School(name="Eldoret High", academic_year="2026")
        db.session.add(school)
        db.session.commit()

        # Generate sample Excel
        sample_path = tmp_path / "sample.xlsx"
        BulkImporter.generate_sample_excel(sample_path)
        assert sample_path.exists()

        # Read back records
        headers, rows = BulkImporter.read_records(sample_path)
        assert len(headers) >= 8
        assert len(rows) == 5

        # Test Auto Mapping
        mapping = BulkImporter.auto_detect_mapping(headers)
        assert "admission_number" in mapping
        assert "full_name" in mapping
        assert "class_name" in mapping

        # Create photo zip with 2 photos: "1001.jpg" and "1002.png"
        zip_path = tmp_path / "photos.zip"
        photo_dir = tmp_path / "extracted_photos"
        with zipfile.ZipFile(zip_path, "w") as zf:
            test_img = Image.new("RGB", (100, 100), color="blue")
            img_p1 = tmp_path / "1001.jpg"
            img_p2 = tmp_path / "1002.png"
            test_img.save(img_p1)
            test_img.save(img_p2)
            zf.write(img_p1, arcname="1001.jpg")
            zf.write(img_p2, arcname="1002.png")

        photo_map = BulkImporter.extract_zip_photos(zip_path, photo_dir)
        assert "1001" in photo_map
        assert "1002" in photo_map

        # Validate rows
        valid_records, invalid_records, errors = BulkImporter.validate_records(
            school_id=school.id,
            rows=rows,
            mapping=mapping,
            photo_map=photo_map,
            academic_year="2026"
        )

        assert len(valid_records) == 5
        assert len(invalid_records) == 0
        assert valid_records[0]["has_photo"] is True
        assert valid_records[1]["has_photo"] is True
        assert valid_records[2]["has_photo"] is False # photo not in zip

        # Commit valid records
        committed = BulkImporter.commit_valid_records(school.id, valid_records)
        assert committed == 5
        assert Student.query.filter_by(school_id=school.id).count() == 5
