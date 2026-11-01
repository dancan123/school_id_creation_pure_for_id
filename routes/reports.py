import io
import csv
from flask import Blueprint, render_template, Response
from flask_login import login_required
from extensions import db
from models import School, Student, CardRecord, AuditLog
from utils import get_current_school

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/")
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    # Core statistics
    total_students = Student.query.filter_by(school_id=school.id, is_archived=False).count()
    cards_generated = CardRecord.query.filter_by(school_id=school.id).count()
    cards_printed = CardRecord.query.filter_by(school_id=school.id, print_status="printed").count()
    cards_pending = CardRecord.query.filter_by(school_id=school.id, print_status="pending").count()
    missing_photos = Student.query.filter_by(school_id=school.id, photo_filename=None, is_archived=False).count()
    reprints_count = CardRecord.query.filter_by(school_id=school.id, status="replaced").count()

    # Class & Stream Breakdown
    class_stats = db.session.query(
        Student.class_name,
        Student.stream_name,
        db.func.count(Student.id).label("total_students"),
        db.func.count(CardRecord.id).label("cards_issued")
    ).outerjoin(CardRecord, CardRecord.student_id == Student.id)\
     .filter(Student.school_id == school.id, Student.is_archived == False)\
     .group_by(Student.class_name, Student.stream_name)\
     .order_by(Student.class_name, Student.stream_name).all()

    # Recent Audit activity
    recent_audits = AuditLog.query.filter_by(school_id=school.id).order_by(AuditLog.created_at.desc()).limit(15).all()

    return render_template(
        "reports/index.html",
        current_school=school,
        all_schools=all_schools,
        total_students=total_students,
        cards_generated=cards_generated,
        cards_printed=cards_printed,
        cards_pending=cards_pending,
        missing_photos=missing_photos,
        reprints_count=reprints_count,
        class_stats=class_stats,
        recent_audits=recent_audits
    )

@reports_bp.route("/export-students-csv")
@login_required
def export_students_csv():
    school = get_current_school()
    students = Student.query.filter_by(school_id=school.id, is_archived=False)\
        .order_by(Student.class_name, Student.admission_number).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Admission Number", "Full Name", "Class", "Stream", "Academic Year",
        "Gender", "Date of Birth", "Parent Phone", "Blood Group", "House/Dorm",
        "Card Status", "Card Number", "Issue Date", "Expiry Date", "Has Photo"
    ])

    for s in students:
        writer.writerow([
            s.admission_number,
            s.full_name,
            s.class_name,
            s.stream_name or "",
            s.academic_year,
            s.gender or "",
            s.dob or "",
            s.parent_phone or "",
            s.blood_group or "",
            s.house_or_dorm or "",
            s.card_status,
            s.card_number or "",
            str(s.issue_date) if s.issue_date else "",
            str(s.expiry_date) if s.expiry_date else "",
            "Yes" if s.photo_filename else "No"
        ])

    filename = f"{school.name.replace(' ', '_')}_students_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
