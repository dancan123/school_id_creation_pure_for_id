import secrets
import base64
import io
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from extensions import db
from models import Student, School
from config import Config
from utils import get_current_school, log_audit, save_uploaded_file

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

students_bp = Blueprint("students", __name__)

def _build_students_filtered_query(school_id):
    """Builds a filtered Student query based on active request parameters."""
    search = request.args.get("search", "").strip()
    class_filter = request.args.get("class", "").strip()
    stream_filter = request.args.get("stream", "").strip()
    status_filter = request.args.get("status", "").strip()
    missing_photo = request.args.get("missing_photo", "").strip()

    query = Student.query.filter_by(school_id=school_id, is_archived=False)

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

    filter_dict = {
        "search": search,
        "class_filter": class_filter,
        "stream_filter": stream_filter,
        "status_filter": status_filter,
        "missing_photo": missing_photo
    }
    return query, filter_dict

@students_bp.route("/")
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    page = int(request.args.get("page", 1))
    query, filters = _build_students_filtered_query(school.id)

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
        search=filters["search"],
        class_filter=filters["class_filter"],
        stream_filter=filters["stream_filter"],
        status_filter=filters["status_filter"],
        missing_photo=filters["missing_photo"]
    )

@students_bp.route("/export/excel")
@login_required
def export_excel():
    school = get_current_school()
    query, filters = _build_students_filtered_query(school.id)
    students = query.order_by(Student.class_name, Student.stream_name, Student.admission_number).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Register"
    ws.views.sheetView[0].showGridLines = True

    # Color styling derived from school theme
    primary_hex = (school.primary_color or "#1E3A8A").lstrip("#")
    if len(primary_hex) != 6:
        primary_hex = "1E3A8A"

    # Title Header Block
    ws.merge_cells("A1:Q1")
    title_cell = ws["A1"]
    title_cell.value = f"{school.name.upper()} - OFFICIAL STUDENT REGISTER"
    title_cell.font = Font(name="Segoe UI", size=14, bold=True, color=primary_hex)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    # Subtitle / Filter Metadata
    ws.merge_cells("A2:Q2")
    sub_cell = ws["A2"]
    filter_desc = []
    if filters["class_filter"]: filter_desc.append(f"Class: {filters['class_filter']}")
    if filters["stream_filter"]: filter_desc.append(f"Stream: {filters['stream_filter']}")
    if filters["status_filter"]: filter_desc.append(f"Card Status: {filters['status_filter']}")
    if filters["missing_photo"] == "1": filter_desc.append("Missing Photos Only")
    scope_txt = f" (Scope: {', '.join(filter_desc)})" if filter_desc else " (All Records)"
    
    sub_cell.value = f"Academic Year: {school.academic_year} | Export Date: {datetime.date.today().strftime('%d %B %Y')} | Total Exported: {len(students)}{scope_txt}"
    sub_cell.font = Font(name="Segoe UI", size=9, italic=True, color="475569")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    # Table Column Headers
    headers = [
        "#", "Admission No", "Full Name", "Class / Grade", "Stream", "Curriculum",
        "Gender", "Date of Birth", "UPI / NEMIS", "Parent / Guardian", "Emergency Contact",
        "Blood Group", "House / Dorm", "Card Status", "Card Number", "Card Expiry", "Photo Uploaded"
    ]

    header_fill = PatternFill(start_color=primary_hex, end_color=primary_hex, fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws.row_dimensions[4].height = 24
    for col_num, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=col_num, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=9)

    for i, s in enumerate(students, 1):
        row_num = 4 + i
        ws.row_dimensions[row_num].height = 19
        row_data = [
            i,
            s.admission_number,
            s.full_name,
            s.class_name,
            s.stream_name or "-",
            s.curriculum_type or "CBC",
            s.gender or "-",
            s.dob or "-",
            s.nemis_upi or "-",
            s.parent_name or "-",
            s.parent_phone or "-",
            s.blood_group or "-",
            s.house_or_dorm or "-",
            (s.card_status or "pending").capitalize(),
            s.card_number or "-",
            s.expiry_date.strftime("%Y-%m-%d") if s.expiry_date else "-",
            "Yes" if s.photo_filename else "No"
        ]
        is_even = (i % 2 == 0)
        for col_num, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=val)
            cell.font = regular_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill
            if col_num in [1, 2, 4, 5, 6, 7, 8, 12, 14, 16, 17]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # Dynamic Column Auto-Width
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row > 2 and cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    clean_school = "".join(c for c in school.name if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
    download_name = f"{clean_school}_Students_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
    
    log_audit("EXPORT_STUDENTS_EXCEL", f"Exported {len(students)} students to Excel for {school.name}")
    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=download_name
    )

@students_bp.route("/export/pdf")
@login_required
def export_pdf():
    school = get_current_school()
    query, filters = _build_students_filtered_query(school.id)
    students = query.order_by(Student.class_name, Student.stream_name, Student.admission_number).all()

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )
    styles = getSampleStyleSheet()

    primary_hex = school.primary_color or "#1E3A8A"
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        textColor=colors.HexColor(primary_hex),
        alignment=1
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5
    )
    cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=cell_style,
        alignment=1
    )
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )

    filter_desc = []
    if filters["class_filter"]: filter_desc.append(f"Class: {filters['class_filter']}")
    if filters["stream_filter"]: filter_desc.append(f"Stream: {filters['stream_filter']}")
    if filters["status_filter"]: filter_desc.append(f"Status: {filters['status_filter']}")
    if filters["missing_photo"] == "1": filter_desc.append("Missing Photos Only")
    scope_txt = f" &bull; Scope: {', '.join(filter_desc)}" if filter_desc else " &bull; Scope: All Records"

    story = []
    story.append(Paragraph(f"<b>{school.name.upper()}</b>", title_style))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(
        f"<b>OFFICIAL STUDENT IDENTIFICATION ROSTER & REGISTER</b><br/>"
        f"Academic Year: {school.academic_year} &bull; Generated: {datetime.date.today().strftime('%d %B %Y')} &bull; "
        f"Total Students: <b>{len(students)}</b>{scope_txt}",
        meta_style
    ))
    story.append(Spacer(1, 4 * mm))

    pdf_headers = ["#", "Adm No", "Full Name", "Class", "Stream", "Curriculum", "Gender", "UPI / NEMIS", "Emergency Contact", "Card Status", "Card Number", "Photo"]
    data = [[Paragraph(h, header_style) for h in pdf_headers]]

    for idx, s in enumerate(students, 1):
        status_color = "#16A34A" if s.card_status == "active" else ("#D97706" if s.card_status == "pending" else "#64748B")
        photo_text = "<font color='#16A34A'><b>Yes</b></font>" if s.photo_filename else "<font color='#DC2626'><b>No</b></font>"
        status_text = f"<font color='{status_color}'><b>{(s.card_status or 'Pending').capitalize()}</b></font>"

        row = [
            Paragraph(str(idx), cell_center),
            Paragraph(f"<b>{s.admission_number}</b>", cell_center),
            Paragraph(s.full_name[:26], cell_style),
            Paragraph(s.class_name, cell_center),
            Paragraph(s.stream_name or "-", cell_center),
            Paragraph(s.curriculum_type or "CBC", cell_center),
            Paragraph(s.gender or "-", cell_center),
            Paragraph(s.nemis_upi or "-", cell_center),
            Paragraph(s.parent_phone or "-", cell_center),
            Paragraph(status_text, cell_center),
            Paragraph(s.card_number or "-", cell_center),
            Paragraph(photo_text, cell_center),
        ]
        data.append(row)

    col_widths = [8*mm, 20*mm, 48*mm, 18*mm, 18*mm, 18*mm, 14*mm, 28*mm, 28*mm, 22*mm, 28*mm, 15*mm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(primary_hex)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t)

    doc.build(story)
    pdf_buffer.seek(0)

    clean_school = "".join(c for c in school.name if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
    download_name = f"{clean_school}_Student_Register_{datetime.date.today().strftime('%Y%m%d')}.pdf"

    log_audit("EXPORT_STUDENTS_PDF", f"Exported {len(students)} students to PDF register for {school.name}")
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name
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
        flash("Student details updated successfully!", "success")
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
