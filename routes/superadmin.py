import datetime
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models import School, User, Student, CardRecord, AuditLog, PlatformAnnouncement
from utils import superadmin_required, log_audit

superadmin_bp = Blueprint("superadmin", __name__, url_prefix="/superadmin")

@superadmin_bp.before_request
@login_required
@superadmin_required
def enforce_superadmin():
    """Double-guard to guarantee that every single route in superadmin blueprint is strictly Super Admin."""
    pass


@superadmin_bp.route("/")
def index():
    """Main Super Admin Dashboard Overview with Platform KPI Metrics."""
    total_schools = School.query.count()
    active_schools = School.query.filter_by(status="active").count()
    pending_schools = School.query.filter_by(status="pending").count()
    suspended_schools = School.query.filter_by(status="suspended").count()

    total_users = User.query.count()
    total_students = Student.query.count()
    total_cards = CardRecord.query.count()
    total_printed_cards = CardRecord.query.filter(CardRecord.print_count > 0).count()

    # Recent pending applications
    pending_list = School.query.filter_by(status="pending").order_by(School.created_at.desc()).limit(5).all()

    # Recent platform audit entries
    recent_audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()

    # Breakdown by institution type
    type_counts = {
        "schools": School.query.filter(School.institution_type.in_(["school", "primary", "secondary"])).count(),
        "universities": School.query.filter(School.institution_type.in_(["university", "college"])).count(),
        "tvets": School.query.filter_by(institution_type="tvet").count(),
        "corporates": School.query.filter(School.institution_type.in_(["company", "corporate", "business"])).count(),
        "ngos": School.query.filter(School.institution_type.in_(["ngo", "organization"])).count()
    }

    return render_template(
        "superadmin/dashboard.html",
        total_schools=total_schools,
        active_schools=active_schools,
        pending_schools=pending_schools,
        suspended_schools=suspended_schools,
        total_users=total_users,
        total_students=total_students,
        total_cards=total_cards,
        total_printed_cards=total_printed_cards,
        pending_list=pending_list,
        recent_audits=recent_audits,
        type_counts=type_counts
    )


@superadmin_bp.route("/organizations")
def organizations():
    """List, search, filter, and paginate all registered institutions."""
    status_filter = request.args.get("status", "all")
    type_filter = request.args.get("type", "all")
    search_q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))

    query = School.query

    if status_filter != "all":
        query = query.filter(School.status == status_filter)

    if type_filter != "all":
        query = query.filter(School.institution_type == type_filter)

    if search_q:
        query = query.filter(
            (School.name.ilike(f"%{search_q}%")) |
            (School.code.ilike(f"%{search_q}%")) |
            (School.county.ilike(f"%{search_q}%")) |
            (School.email.ilike(f"%{search_q}%")) |
            (School.contact_person_name.ilike(f"%{search_q}%"))
        )

    pagination = query.order_by(School.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    return render_template(
        "superadmin/organizations.html",
        pagination=pagination,
        schools=pagination.items,
        status_filter=status_filter,
        type_filter=type_filter,
        search_q=search_q
    )


@superadmin_bp.route("/organizations/<int:school_id>")
def org_detail(school_id):
    """Detailed profile, configuration, usage stats, and users for an institution."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    users = User.query.filter_by(school_id=school.id).all()
    students_count = Student.query.filter_by(school_id=school.id).count()
    cards_count = CardRecord.query.filter_by(school_id=school.id).count()
    recent_logs = AuditLog.query.filter_by(school_id=school.id).order_by(AuditLog.created_at.desc()).limit(15).all()

    return render_template(
        "superadmin/org_detail.html",
        school=school,
        users=users,
        students_count=students_count,
        cards_count=cards_count,
        recent_logs=recent_logs
    )


@superadmin_bp.route("/organizations/<int:school_id>/approve", methods=["POST"])
def approve_org(school_id):
    """Approve a pending institution and activate its admin account."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    school.status = "active"
    school.is_active = True
    school.approved_at = datetime.datetime.utcnow()
    school.approved_by_user_id = current_user.id
    school.rejection_reason = None

    # Activate associated owner user
    owner = User.query.filter_by(school_id=school.id, role="org_owner").first()
    if owner:
        owner.is_active = True

    db.session.commit()
    log_audit("SUPERADMIN_APPROVE_INSTITUTION", f"Approved institution '{school.name}' (ID: {school.id})", school_id=school.id)
    flash(f"Institution '{school.name}' has been approved and activated successfully!", "success")
    return redirect(url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/reject", methods=["POST"])
def reject_org(school_id):
    """Reject a pending institution with an explanation."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    reason = request.form.get("reason", "Verification credentials could not be validated.").strip()
    school.status = "rejected"
    school.is_active = False
    school.rejection_reason = reason

    owner = User.query.filter_by(school_id=school.id, role="org_owner").first()
    if owner:
        owner.is_active = False

    db.session.commit()
    log_audit("SUPERADMIN_REJECT_INSTITUTION", f"Rejected institution '{school.name}' (ID: {school.id}). Reason: {reason}", school_id=school.id)
    flash(f"Institution '{school.name}' registration marked as rejected.", "warning")
    return redirect(url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/suspend", methods=["POST"])
def suspend_org(school_id):
    """Suspend an active institution."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    school.status = "suspended"
    db.session.commit()
    log_audit("SUPERADMIN_SUSPEND_INSTITUTION", f"Suspended institution '{school.name}' (ID: {school.id})", school_id=school.id)
    flash(f"Institution '{school.name}' has been suspended.", "warning")
    return redirect(url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/reactivate", methods=["POST"])
def reactivate_org(school_id):
    """Reactivate a suspended institution."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    school.status = "active"
    school.is_active = True
    db.session.commit()
    log_audit("SUPERADMIN_REACTIVATE_INSTITUTION", f"Reactivated institution '{school.name}' (ID: {school.id})", school_id=school.id)
    flash(f"Institution '{school.name}' reactivated successfully.", "success")
    return redirect(url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/delete", methods=["POST"])
def delete_org(school_id):
    """Permanently delete an institution and all its associated data (Super Admin only)."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    school_name = school.name
    db.session.delete(school)
    db.session.commit()

    log_audit("SUPERADMIN_DELETE_INSTITUTION", f"Permanently deleted institution '{school_name}' (ID: {school_id})")
    flash(f"Institution '{school_name}' and all associated records have been permanently deleted.", "success")
    return redirect(url_for("superadmin.organizations"))


@superadmin_bp.route("/organizations/<int:school_id>/update-tier", methods=["POST"])
def update_tier(school_id):
    """Set custom ID generation limit and subscription plan tier."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    tier = request.form.get("subscription_tier", school.subscription_tier or "standard")
    try:
        quota = int(request.form.get("max_cards_quota", 2))
    except (ValueError, TypeError):
        quota = 2

    school.subscription_tier = tier
    school.max_cards_quota = max(0, quota)
    # Refresh actual generated count from DB
    school.cards_generated_count = CardRecord.query.filter_by(school_id=school.id).count()
    db.session.commit()

    log_audit("SUPERADMIN_SET_ID_LIMIT", f"Set ID limit for {school.name} to {quota} cards (Tier: {tier})", school_id=school.id)
    flash(f"ID generation limit for '{school.name}' successfully set to {quota} cards ({tier.replace('_', ' ').title()}).", "success")
    return redirect(request.referrer or url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/reset-admin-password", methods=["POST"])
def reset_admin_password(school_id):
    """Reset administrator password for an institution."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    new_pass = request.form.get("new_password", "").strip()
    if not new_pass or len(new_pass) < 6:
        flash("Password must be at least 6 characters long.", "danger")
        return redirect(url_for("superadmin.org_detail", school_id=school.id))

    owner = User.query.filter_by(school_id=school.id, role="org_owner").first() or \
            User.query.filter_by(school_id=school.id).first()

    if not owner:
        flash("No administrator user account found for this institution.", "danger")
        return redirect(url_for("superadmin.org_detail", school_id=school.id))

    owner.set_password(new_pass)
    owner.failed_login_attempts = 0
    owner.locked_until = None
    db.session.commit()

    log_audit("SUPERADMIN_RESET_PASSWORD", f"Reset admin password for user {owner.username} in {school.name}", school_id=school.id)
    flash(f"Admin password for '{owner.username}' successfully reset.", "success")
    return redirect(url_for("superadmin.org_detail", school_id=school.id))


@superadmin_bp.route("/organizations/<int:school_id>/enter-workspace")
def enter_workspace(school_id):
    """Super Admin switches into an organisation's workspace in inspection mode."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution not found.", "danger")
        return redirect(url_for("superadmin.organizations"))

    session["active_school_id"] = school.id
    log_audit("SUPERADMIN_INSPECT_WORKSPACE", f"Superadmin entered workspace for {school.name}", school_id=school.id)
    flash(f"Now inspecting workspace: {school.name}. You have Platform Super Admin access.", "info")
    return redirect(url_for("dashboard.index"))


@superadmin_bp.route("/users")
def users():
    """Platform-wide directory of all users across institutions."""
    page = int(request.args.get("page", 1))
    search_q = request.args.get("q", "").strip()

    query = User.query
    if search_q:
        query = query.filter(
            (User.username.ilike(f"%{search_q}%")) |
            (User.email.ilike(f"%{search_q}%")) |
            (User.full_name.ilike(f"%{search_q}%"))
        )

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "superadmin/users.html",
        pagination=pagination,
        users=pagination.items,
        search_q=search_q
    )


@superadmin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
def toggle_user_status(user_id):
    """Activate or deactivate any user account across the platform."""
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("superadmin.users"))

    if user.id == current_user.id:
        flash("You cannot deactivate your own current Super Admin account.", "danger")
        return redirect(url_for("superadmin.users"))

    user.is_active = not user.is_active
    db.session.commit()

    action_label = "activated" if user.is_active else "deactivated"
    log_audit("SUPERADMIN_TOGGLE_USER_STATUS", f"{action_label.capitalize()} user {user.username} (ID: {user.id})")
    flash(f"User '{user.username}' has been {action_label}.", "success")
    return redirect(request.referrer or url_for("superadmin.users"))


@superadmin_bp.route("/audit")
def audit():
    """Global system-wide security, card generation, and operational audit trail."""
    page = int(request.args.get("page", 1))
    search_q = request.args.get("q", "").strip()

    query = AuditLog.query
    if search_q:
        query = query.filter(
            (AuditLog.action.ilike(f"%{search_q}%")) |
            (AuditLog.details.ilike(f"%{search_q}%")) |
            (AuditLog.username.ilike(f"%{search_q}%"))
        )

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "superadmin/audit.html",
        pagination=pagination,
        logs=pagination.items,
        search_q=search_q
    )


@superadmin_bp.route("/announcements", methods=["GET", "POST"])
def announcements():
    """Broadcast platform notifications to tenant workspaces."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        severity = request.form.get("severity", "info").strip()

        if title and message:
            announcement = PlatformAnnouncement(
                title=title,
                message=message,
                severity=severity,
                is_active=True
            )
            db.session.add(announcement)
            db.session.commit()
            log_audit("SUPERADMIN_CREATE_ANNOUNCEMENT", f"Broadcast announcement: {title}")
            flash("Platform announcement broadcasted successfully.", "success")
            return redirect(url_for("superadmin.announcements"))

    all_announcements = PlatformAnnouncement.query.order_by(PlatformAnnouncement.created_at.desc()).all()
    return render_template("superadmin/announcements.html", announcements=all_announcements)
