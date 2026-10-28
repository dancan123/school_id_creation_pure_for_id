import base64
import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from extensions import db
from models import Student, School, CardRecord
from config import Config
from utils import get_current_school, log_audit, save_uploaded_file

students_bp = Blueprint("students", __name__)

@students_bp.route("/")
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    # Filters
    search = request.args.get("search", "").strip()
    class_filter = request.args.get("class", "").strip()
    stream_filter = request.args.get("stream", "").strip()
    status_filter = request.args.get("status", "").strip()
    missing_photo = request.args.get("missing_photo", "").strip()
    page = int(request.args.get("page", 1))

    query = Student.query.filter_by(school_id=school.id, is_archived=False)

    if search:
        query = query.filter((Student.admission_number.ilike(f"%{search}%")) | (Student.full_name.ilike(f"%{search}%")))
    if class_filter:
        query = query.filter(Student.class_name == class_filter)
    if stream_filter:
        query = query.filter(Student.stream_name == stream_filter)
    if status_filter:
        query = query.filter(Student.card_status == status_filter)
    if missing_photo == "1":
        query = query.filter(Student.photo_filename == None)

    # Distinct classes and streams for dropdowns
    classes = [r[0] for r in db.session.query(Student.class_name).filter_by(school_id=school.id, is_archived=False).distinct().order_by(Student.class_name).all()]
    streams = [r[0] for r in db.session.query(Student.stream_name).filter_by(school_id=school.id, is_archived=False).filter(Student.stream_name != None).distinct().order_by(Student.stream_name).all()]

    pagination = query.order_by(Student.class_name, Student.admission_number).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "students/index.html",
        current_school=school,
        all_schools=all_schools,
        students=pagination.items,
        pagination=pagination,
        classes=classes,
        streams=streams,
        search=search,
        class_filter=class_filter,
        stream_filter=stream_filter,
        status_filter=status_filter,
        missing_photo=missing_photo
    )

@students_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_student():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    if request.method == "POST":
        adm_no = request.form.get("admission_number", "").strip()
        full_name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        curriculum_type = request.form.get("curriculum_type", "CBC").strip()
        stream_name = request.form.get("stream_name", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        dob = request.form.get("dob", "").strip() or None
        parent_name = request.form.get("parent_name", "").strip() or None
        parent_phone = request.form.get("parent_phone", "").strip() or None
        blood_group = request.form.get("blood_group", "").strip() or None
        house_or_dorm = request.form.get("house_or_dorm", "").strip() or None
        academic_year = request.form.get("academic_year", school.academic_year).strip()

        if not adm_no or not full_name or not class_name:
            flash("Admission Number, Full Name, and Class are required fields.", "danger")
            return redirect(url_for("students.new_student"))

        # Prevent duplicate admission number within same school
        existing = Student.query.filter_by(school_id=school.id, admission_number=adm_no).first()
        if existing:
            flash(f"Student with Admission Number '{adm_no}' is already registered in {school.name}.", "danger")
            return redirect(url_for("students.new_student"))

        photo_fn = None
        # Handle file upload or webcam base64
        webcam_data = request.form.get("webcam_image_data")
        if webcam_data and "," in webcam_data:
            try:
                header, encoded = webcam_data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                unique_fn = f"photo_{school.id}_{adm_no}_{secrets.token_hex(4)}.jpg"
                with open(Config.PHOTOS_DIR / unique_fn, "wb") as f:
                    f.write(img_bytes)
                photo_fn = unique_fn
            except Exception as e:
                flash(f"Failed to save webcam photo: {e}", "warning")
        elif "photo_file" in request.files:
            pf = request.files["photo_file"]
            if pf and pf.filename:
                photo_fn = save_uploaded_file(pf, Config.PHOTOS_DIR, prefix=f"photo_{school.id}_{adm_no}_")

        student = Student(
            school_id=school.id,
            admission_number=adm_no,
            full_name=full_name,
            curriculum_type=curriculum_type,
            class_name=class_name,
            stream_name=stream_name,
            gender=gender,
            dob=dob,
            parent_name=parent_name,
            parent_phone=parent_phone,
            blood_group=blood_group,
            house_or_dorm=house_or_dorm,
            academic_year=academic_year,
            photo_filename=photo_fn,
            card_status="pending"
        )
        db.session.add(student)
        db.session.commit()

        flash(f"Student '{student.full_name}' ({student.admission_number}) registered successfully!", "success")
        log_audit("CREATE_STUDENT", f"Registered student {adm_no} in {school.name}")

        # Check if user clicked "Save & Generate Card"
        if "save_and_generate" in request.form:
            return redirect(url_for("single_id.generate_card", student_id=student.id))

        return redirect(url_for("students.index"))

    return render_template("students/form.html", current_school=school, all_schools=all_schools, student=None)

@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    all_schools = School.query.filter_by(is_active=True).all()

    if request.method == "POST":
        adm_no = request.form.get("admission_number", "").strip()
        full_name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        curriculum_type = request.form.get("curriculum_type", student.curriculum_type or "CBC").strip()
        stream_name = request.form.get("stream_name", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        dob = request.form.get("dob", "").strip() or None
        parent_name = request.form.get("parent_name", "").strip() or None
        parent_phone = request.form.get("parent_phone", "").strip() or None
        blood_group = request.form.get("blood_group", "").strip() or None
        house_or_dorm = request.form.get("house_or_dorm", "").strip() or None
        academic_year = request.form.get("academic_year", student.academic_year).strip()

        if not adm_no or not full_name or not class_name:
            flash("Admission Number, Full Name, and Class are required fields.", "danger")
            return redirect(url_for("students.edit_student", student_id=student.id))

        # Check duplicate admission number if changed
        if adm_no != student.admission_number:
            existing = Student.query.filter_by(school_id=school.id, admission_number=adm_no).first()
            if existing and existing.id != student.id:
                flash(f"Admission Number '{adm_no}' is already used by another student.", "danger")
                return redirect(url_for("students.edit_student", student_id=student.id))

        student.admission_number = adm_no
        student.full_name = full_name
        student.curriculum_type = curriculum_type
        student.class_name = class_name
        student.stream_name = stream_name
        student.gender = gender
        student.dob = dob
        student.parent_name = parent_name
        student.parent_phone = parent_phone
        student.blood_group = blood_group
        student.house_or_dorm = house_or_dorm
        student.academic_year = academic_year

        # Photo update
        webcam_data = request.form.get("webcam_image_data")
        if webcam_data and "," in webcam_data:
            try:
                import secrets
                header, encoded = webcam_data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                unique_fn = f"photo_{school.id}_{adm_no}_{secrets.token_hex(4)}.jpg"
                with open(Config.PHOTOS_DIR / unique_fn, "wb") as f:
                    f.write(img_bytes)
                student.photo_filename = unique_fn
            except Exception as e:
                flash(f"Failed to save webcam photo: {e}", "warning")
        elif "photo_file" in request.files:
            pf = request.files["photo_file"]
            if pf and pf.filename:
                student.photo_filename = save_uploaded_file(pf, Config.PHOTOS_DIR, prefix=f"photo_{school.id}_{adm_no}_")

        db.session.commit()
        flash(f"Student details updated successfully!", "success")
        log_audit("EDIT_STUDENT", f"Updated student {adm_no}")
        return redirect(url_for("students.index"))

    return render_template("students/form.html", current_school=school, all_schools=all_schools, student=student)

@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    adm = student.admission_number
    db.session.delete(student)
    db.session.commit()
    flash(f"Student '{adm}' has been deleted.", "info")
    log_audit("DELETE_STUDENT", f"Deleted student {adm}")
    return redirect(url_for("students.index"))
