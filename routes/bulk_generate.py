import uuid
import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required
from extensions import db
from models import School, Student, GenerationJob
from config import Config
from utils import get_current_school, log_audit
from services.bulk_generator import BulkGenerator

bulk_generate_bp = Blueprint("bulk_generate", __name__)

@bulk_generate_bp.route("/", methods=["GET"])
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    # Classes and Streams
    classes = [r[0] for r in db.session.query(Student.class_name).filter_by(school_id=school.id, is_archived=False).distinct().order_by(Student.class_name).all()]
    streams = [r[0] for r in db.session.query(Student.stream_name).filter_by(school_id=school.id, is_archived=False).filter(Student.stream_name != None).distinct().order_by(Student.stream_name).all()]

    # Real-Time Operational Telemetry
    total_eligible = Student.query.filter_by(school_id=school.id, is_archived=False).count()
    active_cards_count = Student.query.filter_by(school_id=school.id, card_status="active", is_archived=False).count()
    pending_cards_count = Student.query.filter_by(school_id=school.id, is_archived=False).filter(Student.card_status != "active").count()
    missing_photos_count = Student.query.filter_by(school_id=school.id, photo_filename=None, is_archived=False).count()

    # Recent generation jobs
    jobs = GenerationJob.query.filter_by(school_id=school.id).order_by(GenerationJob.created_at.desc()).limit(20).all()

    return render_template(
        "bulk_generate/index.html",
        current_school=school,
        all_schools=all_schools,
        classes=classes,
        streams=streams,
        total_eligible=total_eligible,
        active_cards_count=active_cards_count,
        pending_cards_count=pending_cards_count,
        missing_photos_count=missing_photos_count,
        jobs=jobs
    )

@bulk_generate_bp.route("/start", methods=["POST"])
@login_required
def start_generation():
    school = get_current_school()
    scope = request.form.get("scope", "all")
    class_filter = request.form.get("class_name")
    stream_filter = request.form.get("stream_name")
    card_status_filter = request.form.get("card_status_filter", "pending")
    photo_filter = request.form.get("photo_filter", "all")
    print_format = request.form.get("print_format", "cr80_single")

    query = Student.query.filter_by(school_id=school.id, is_archived=False)

    if scope == "class" and class_filter:
        query = query.filter(Student.class_name == class_filter)
        if stream_filter:
            query = query.filter(Student.stream_name == stream_filter)
    elif scope == "pending":
        query = query.filter(Student.card_status != "active")

    # Apply card status filter
    if card_status_filter == "pending":
        query = query.filter(Student.card_status != "active")

    # Apply photo filter
    if photo_filter == "with_photo":
        query = query.filter(Student.photo_filename != None)

    student_records = query.all()
    if not student_records:
        flash("No students found matching the selected batch criteria.", "warning")
        return redirect(url_for("bulk_generate.index"))

    student_ids = [s.id for s in student_records]

    job_id = str(uuid.uuid4())
    desc_scope = f"{scope.capitalize()}"
    if class_filter: desc_scope += f": {class_filter}"
    if stream_filter: desc_scope += f" ({stream_filter})"
    if card_status_filter == "pending": desc_scope += " [Pending Only]"

    job = GenerationJob(
        id=job_id,
        school_id=school.id,
        template_id=school.default_template_id,
        target_scope=desc_scope,
        total_count=len(student_ids),
        processed_count=0,
        success_count=0,
        failed_count=0,
        status="queued",
        print_format=print_format
    )
    db.session.add(job)
    db.session.commit()

    base_url = request.host_url.rstrip("/")

    # Execute generation
    BulkGenerator.run_generation(
        job_id=job_id,
        school_id=school.id,
        student_ids=student_ids,
        print_format=print_format,
        base_url=base_url
    )

    log_audit("BULK_GENERATE_CARDS", f"Generated {len(student_ids)} cards for {school.name} (Format: {print_format})")
    flash(f"Batch generation completed! Generated cards for {len(student_ids)} students.", "success")

    return redirect(url_for("bulk_generate.index"))

@bulk_generate_bp.route("/download/<job_id>")
@login_required
def download_batch_pdf(job_id):
    school = get_current_school()
    job = GenerationJob.query.filter_by(id=job_id, school_id=school.id).first_or_404()

    if not job.pdf_filename:
        flash("PDF has not been generated for this job.", "danger")
        return redirect(url_for("bulk_generate.index"))

    pdf_path = Config.PDFS_DIR / job.pdf_filename
    if not pdf_path.exists():
        flash("PDF file not found on disk.", "danger")
        return redirect(url_for("bulk_generate.index"))

    log_audit("DOWNLOAD_BATCH_PDF", f"Downloaded PDF for batch {job_id}")

    clean_school = "".join(c for c in school.name if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
    return send_file(
        str(pdf_path),
        as_attachment=True,
        download_name=f"{clean_school}_{job.print_format}_{job.created_at.strftime('%Y%m%d')}.pdf"
    )

@bulk_generate_bp.route("/download-zip/<job_id>")
@login_required
def download_batch_zip(job_id):
    school = get_current_school()
    job = GenerationJob.query.filter_by(id=job_id, school_id=school.id).first_or_404()

    zip_path = BulkGenerator.ensure_batch_zip(job_id)
    if not zip_path or not zip_path.exists():
        flash("Could not compile 300 DPI card images for this batch.", "danger")
        return redirect(url_for("bulk_generate.index"))

    log_audit("DOWNLOAD_BATCH_ZIP", f"Downloaded 300 DPI Cards ZIP for batch {job_id}")

    clean_school = "".join(c for c in school.name if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
    return send_file(
        str(zip_path),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{clean_school}_Batch_{job_id[:8]}_Cards_300DPI.zip"
    )
