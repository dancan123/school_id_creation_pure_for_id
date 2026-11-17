from flask import Blueprint, render_template, url_for, redirect, flash
from flask_login import current_user
from extensions import db
from models import School, Student, CardRecord, GenerationJob, SelfEnrolment, PlatformAnnouncement, PaymentTransaction
from utils import get_current_school

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def index():
    # Public visitors see the modern SaaS landing page
    if not current_user.is_authenticated:
        return render_template("landing.html")

    # Super Admin direct to Super Admin console
    if getattr(current_user, "is_platform_admin", False) or current_user.role == "superadmin":
        return redirect(url_for("superadmin.index"))

    school = get_current_school()
    if not school:
        flash("No active institution found.", "warning")
        return redirect(url_for("auth.login"))

    # Multi-tenant status checks
    if school.status == "pending":
        flash("Your institution application is pending Super Admin review.", "warning")
        return redirect(url_for("auth.registration_status", school_id=school.id))
    elif school.status == "suspended" or not school.is_active:
        return redirect(url_for("auth.tenant_suspended"))
    all_schools = School.query.filter_by(is_active=True).all()
    announcements = PlatformAnnouncement.query.filter_by(is_active=True).order_by(PlatformAnnouncement.created_at.desc()).limit(3).all()

    # Calculate statistics for the active school
    total_students = Student.query.filter_by(school_id=school.id, is_archived=False).count()
    cards_generated = CardRecord.query.filter_by(school_id=school.id).count()
    cards_printed = CardRecord.query.filter_by(school_id=school.id, print_status="printed").count()
    cards_pending = CardRecord.query.filter_by(school_id=school.id, print_status="pending").count()
    missing_photos = Student.query.filter_by(school_id=school.id, photo_filename=None, is_archived=False).count()
    pending_enrolments = SelfEnrolment.query.filter_by(school_id=school.id, status="pending").count()

    # Class breakdown
    classes = db.session.query(Student.class_name, db.func.count(Student.id))\
        .filter_by(school_id=school.id, is_archived=False)\
        .group_by(Student.class_name).all()

    # Recent generation jobs
    recent_jobs = GenerationJob.query.filter_by(school_id=school.id)\
        .order_by(GenerationJob.created_at.desc()).limit(5).all()

    # Recent students
    recent_students = Student.query.filter_by(school_id=school.id, is_archived=False)\
        .order_by(Student.created_at.desc()).limit(8).all()

    # Recent Billing & Payment Transactions for Receipt Downloads
    recent_transactions = PaymentTransaction.query.filter_by(school_id=school.id)\
        .order_by(PaymentTransaction.created_at.desc()).limit(10).all()

    onboard_url = url_for("enrolment.self_enrol", school_code=school.code or school.id, _external=True)

    return render_template(
        "dashboard/index.html",
        current_school=school,
        all_schools=all_schools,
        total_students=total_students,
        cards_generated=cards_generated,
        cards_printed=cards_printed,
        cards_pending=cards_pending,
        missing_photos=missing_photos,
        pending_enrolments=pending_enrolments,
        classes=classes,
        recent_jobs=recent_jobs,
        recent_students=recent_students,
        onboard_url=onboard_url,
        announcements=announcements,
        recent_transactions=recent_transactions
    )
