import io
import csv
import re
import datetime
from flask import Blueprint, render_template, Response
from flask_login import login_required
from extensions import db
from models import School, Student, CardRecord, AuditLog, GateScanLog, ApiKey
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

    # Dynamic taxonomy breakdown by class / department / stream
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
        recent_audits=recent_audits,
        id_label=school.get_id_label() if school else "ADM NO",
        member_label=school.get_member_label() if school else "Member",
        member_label_plural=school.get_member_label_plural() if school else "Members",
        class_label=school.get_class_label() if school else "Class / Department",
        stream_label=school.get_stream_label() if school else "Stream / Job Title"
    )

@reports_bp.route("/export-students-csv")
@login_required
def export_students_csv():
    school = get_current_school()
    students = Student.query.filter_by(school_id=school.id, is_archived=False)\
        .order_by(Student.class_name, Student.admission_number).all()

    id_label = school.get_id_label() if school else "ID Number"
    member_label = school.get_member_label() if school else "Member"
    class_label = school.get_class_label() if school else "Class / Department"
    stream_label = school.get_stream_label() if school else "Stream / Job Title"
    upi_label = school.get_upi_label() if school else "NEMIS / National ID"
    year_label = school.get_academic_year_label() if school else "Academic Year"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        id_label,
        f"{member_label} Full Name",
        class_label,
        stream_label,
        year_label,
        "Gender",
        "Date of Birth",
        upi_label,
        "Emergency / Contact Phone",
        "Blood Group",
        "Station / House",
        "Card Status",
        "Card Serial Number",
        "Issue Date",
        "Expiry Date",
        "Has Photo"
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
            s.nemis_upi or "",
            s.parent_phone or "",
            s.blood_group or "",
            s.house_or_dorm or "",
            (s.card_status or "pending").capitalize(),
            s.card_number or "",
            str(s.issue_date) if s.issue_date else "",
            str(s.expiry_date) if s.expiry_date else "",
            "Yes" if s.photo_filename else "No"
        ])

    safe_school = re.sub(r"[^A-Za-z0-9_-]+", "_", school.code or school.name).strip("_")
    safe_member = re.sub(r"[^A-Za-z0-9_-]+", "_", school.get_member_label_plural()).lower()
    filename = f"{safe_school}_{safe_member}_manifest_{datetime.date.today().strftime('%Y%m%d')}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@reports_bp.route("/gate-traffic")
@login_required
def gate_traffic():
    """Security Access Control, Turnstile Scans & Real-Time Campus Traffic Analytics."""
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    now_utc = datetime.datetime.utcnow()
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    total_scans_today = GateScanLog.query.filter(GateScanLog.school_id == school.id, GateScanLog.scanned_at >= today_start).count()
    unique_members_today = db.session.query(db.func.count(db.func.distinct(GateScanLog.student_id)))\
        .filter(GateScanLog.school_id == school.id, GateScanLog.scanned_at >= today_start, GateScanLog.scan_status == "granted").scalar() or 0
    denied_scans_today = GateScanLog.query.filter(GateScanLog.school_id == school.id, GateScanLog.scanned_at >= today_start, GateScanLog.scan_status != "granted").count()
    active_devices_count = db.session.query(db.func.count(db.func.distinct(GateScanLog.gate_device))).filter(GateScanLog.school_id == school.id).scalar() or 0

    # Hourly distribution for peak hours (6 AM to 8 PM EAT)
    hourly_distribution = [
        {"hour": f"{h:02d}:00", "count": 0} for h in range(6, 21)
    ]
    today_scans = GateScanLog.query.filter(GateScanLog.school_id == school.id, GateScanLog.scanned_at >= today_start).all()
    for scan in today_scans:
        eat_time = scan.scanned_at + datetime.timedelta(hours=3) # UTC+3 EAT
        h = eat_time.hour
        if 6 <= h <= 20:
            idx = h - 6
            hourly_distribution[idx]["count"] += 1

    max_hourly = max([item["count"] for item in hourly_distribution] or [1])

    recent_scans = GateScanLog.query.filter_by(school_id=school.id).order_by(GateScanLog.scanned_at.desc()).limit(50).all()

    return render_template(
        "reports/gate_traffic.html",
        current_school=school,
        all_schools=all_schools,
        total_scans_today=total_scans_today,
        unique_members_today=unique_members_today,
        denied_scans_today=denied_scans_today,
        active_devices_count=active_devices_count,
        hourly_distribution=hourly_distribution,
        max_hourly=max_hourly,
        recent_scans=recent_scans,
        id_label=school.get_id_label() if school else "ID NO",
        member_label=school.get_member_label() if school else "Member",
        class_label=school.get_class_label() if school else "Department",
        stream_label=school.get_stream_label() if school else "Role"
    )


@reports_bp.route("/gate-traffic/export.csv")
@login_required
def export_gate_traffic_csv():
    """Exports gate verification history log for security compliance and audit."""
    school = get_current_school()
    scans = GateScanLog.query.filter_by(school_id=school.id).order_by(GateScanLog.scanned_at.desc()).limit(1000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Scan Timestamp (EAT)",
        "Member Full Name",
        school.get_id_label() if school else "ID NO",
        school.get_class_label() if school else "Department",
        school.get_stream_label() if school else "Role",
        "Scan Status",
        "Gate Device / Scanner Name",
        "Token Excerpt"
    ])

    for s in scans:
        eat_time = (s.scanned_at + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S") if s.scanned_at else "N/A"
        writer.writerow([
            eat_time,
            s.member_name or "N/A",
            s.admission_number or "N/A",
            s.department or "N/A",
            s.role_title or "N/A",
            (s.scan_status or "granted").upper(),
            s.gate_device or "Mobile Scanner",
            (s.token[:8] + "...") if s.token else "N/A"
        ])

    safe_school = re.sub(r"[^A-Za-z0-9_-]+", "_", school.code or school.name).strip("_")
    filename = f"{safe_school}_gate_traffic_log_{datetime.date.today().strftime('%Y%m%d')}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
