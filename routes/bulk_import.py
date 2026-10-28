import os
import uuid
import json
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session, Response
from flask_login import login_required
from extensions import db
from models import School, ImportJob
from config import Config
from utils import get_current_school, log_audit
from services.bulk_importer import BulkImporter

bulk_import_bp = Blueprint("bulk_import", __name__)

@bulk_import_bp.route("/template")
@login_required
def download_template():
    """Generates and serves the standard Kenyan school Excel student import template."""
    template_path = Config.UPLOADS_DIR / "sample_student_import_template.xlsx"
    BulkImporter.generate_sample_excel(template_path)
    return send_file(
        str(template_path),
        as_attachment=True,
        download_name="Kenyan_School_Student_Import_Template.xlsx"
    )

@bulk_import_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    if request.method == "POST":
        data_file = request.files.get("data_file")
        photos_zip = request.files.get("photos_zip")

        if not data_file or not data_file.filename:
            flash("Please select an Excel (.xlsx/.xls) or CSV file.", "danger")
            return redirect(url_for("bulk_import.upload"))

        ext = Path(data_file.filename).suffix.lower()
        if ext not in {".xlsx", ".xls", ".csv"}:
            flash("Only Excel (.xlsx/.xls) and CSV (.csv) files are supported.", "danger")
            return redirect(url_for("bulk_import.upload"))

        job_id = str(uuid.uuid4())
        job_dir = Config.UPLOADS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        saved_data_path = job_dir / data_file.filename
        data_file.save(str(saved_data_path))

        # Handle photos zip if provided
        photo_map = {}
        if photos_zip and photos_zip.filename and photos_zip.filename.endswith(".zip"):
            zip_save_path = job_dir / photos_zip.filename
            photos_zip.save(str(zip_save_path))
            photo_map = BulkImporter.extract_zip_photos(zip_save_path, Config.PHOTOS_DIR)

        # Store job info in session
        session["import_job"] = {
            "job_id": job_id,
            "school_id": school.id,
            "data_file_path": str(saved_data_path),
            "original_filename": data_file.filename,
            "photo_map": photo_map
        }

        return redirect(url_for("bulk_import.mapping"))

    return render_template("bulk_import/upload.html", current_school=school, all_schools=all_schools)

@bulk_import_bp.route("/mapping", methods=["GET", "POST"])
@login_required
def mapping():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    job_info = session.get("import_job")

    if not job_info:
        flash("Please upload an import file first.", "warning")
        return redirect(url_for("bulk_import.upload"))

    data_file_path = job_info["data_file_path"]
    headers, rows = BulkImporter.read_records(data_file_path)

    if not headers or not rows:
        flash("The uploaded file contains no data or could not be read.", "danger")
        return redirect(url_for("bulk_import.upload"))

    auto_map = BulkImporter.auto_detect_mapping(headers)

    if request.method == "POST":
        # Form submission: read manual mappings
        selected_mapping = {
            "admission_number": request.form.get("map_admission_number"),
            "full_name": request.form.get("map_full_name"),
            "class_name": request.form.get("map_class_name"),
            "stream_name": request.form.get("map_stream_name"),
            "gender": request.form.get("map_gender"),
            "dob": request.form.get("map_dob"),
            "parent_phone": request.form.get("map_parent_phone"),
            "blood_group": request.form.get("map_blood_group"),
            "house_or_dorm": request.form.get("map_house_or_dorm")
        }

        job_info["mapping"] = selected_mapping
        session["import_job"] = job_info
        return redirect(url_for("bulk_import.validate"))

    return render_template(
        "bulk_import/mapping.html",
        current_school=school,
        all_schools=all_schools,
        headers=headers,
        auto_map=auto_map,
        total_rows=len(rows),
        preview_rows=rows[:5]
    )

@bulk_import_bp.route("/validate", methods=["GET"])
@login_required
def validate():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    job_info = session.get("import_job")

    if not job_info or "mapping" not in job_info:
        flash("Session expired or missing mapping. Please restart import.", "warning")
        return redirect(url_for("bulk_import.upload"))

    headers, rows = BulkImporter.read_records(job_info["data_file_path"])
    photo_map = job_info.get("photo_map", {})
    mapping = job_info["mapping"]

    valid_records, invalid_records, errors_list = BulkImporter.validate_records(
        school_id=school.id,
        rows=rows,
        mapping=mapping,
        photo_map=photo_map,
        academic_year=school.academic_year
    )

    # Save validation results in session for committing or error export
    session["validated_valid_records"] = valid_records
    session["validation_errors"] = errors_list

    return render_template(
        "bulk_import/validate.html",
        current_school=school,
        all_schools=all_schools,
        total_records=len(rows),
        valid_records=valid_records,
        invalid_records=invalid_records,
        errors_list=errors_list,
        photo_match_count=sum(1 for r in valid_records if r.get("has_photo"))
    )

@bulk_import_bp.route("/errors-csv")
@login_required
def export_errors_csv():
    errors = session.get("validation_errors", [])
    if not errors:
        flash("No error log available.", "info")
        return redirect(url_for("bulk_import.upload"))

    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Row Number", "Admission Number", "Student Name", "Validation Error"])
    for e in errors:
        writer.writerow([e["row"], e["admission_number"], e["name"], e["error"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=import_validation_errors.csv"}
    )

@bulk_import_bp.route("/commit", methods=["POST"])
@login_required
def commit_import():
    school = get_current_school()
    valid_records = session.get("validated_valid_records", [])

    if not valid_records:
        flash("No valid records to import.", "warning")
        return redirect(url_for("bulk_import.upload"))

    imported_count = BulkImporter.commit_valid_records(school.id, valid_records)

    log_audit("BULK_IMPORT_STUDENTS", f"Imported {imported_count} students for {school.name}")
    flash(f"Successfully imported {imported_count} student records into {school.name}!", "success")

    # Clean up session
    session.pop("import_job", None)
    session.pop("validated_valid_records", None)
    session.pop("validation_errors", None)

    return redirect(url_for("students.index"))
