from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from extensions import db
from models import School, User, AuditLog
from utils import get_current_school, log_audit
from services.backup_service import BackupService

system_bp = Blueprint("system", __name__)

@system_bp.route("/backup")
@login_required
def backup():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    return render_template("system/backup.html", current_school=school, all_schools=all_schools)

@system_bp.route("/backup/create", methods=["POST"])
@login_required
def create_backup():
    try:
        backup_fn, backup_path = BackupService.create_full_backup()
        log_audit("SYSTEM_BACKUP", f"Created backup: {backup_fn}")
        return send_file(str(backup_path), as_attachment=True, download_name=backup_fn)
    except Exception as e:
        flash(f"Failed to create backup: {e}", "danger")
        return redirect(url_for("system.backup"))

@system_bp.route("/seed-demo", methods=["POST", "GET"])
@login_required
def seed_demo():
    try:
        from seed_demo import seed_demo_data
        seed_demo_data()
        flash("Demo student 00100 and sample cohort loaded successfully!", "success")
        log_audit("SEED_DEMO_DATA", "Loaded demo student 00100 and sample school cohort")
    except Exception as e:
        flash(f"Error seeding demo data: {e}", "danger")
    return redirect(url_for("dashboard.index"))

@system_bp.route("/backup/restore", methods=["POST"])
@login_required
def restore_backup():
    restore_file = request.files.get("backup_file")
    if not restore_file or not restore_file.filename.endswith(".zip"):
        flash("Please upload a valid .zip backup archive.", "danger")
        return redirect(url_for("system.backup"))

    try:
        import secrets
        from config import Config
        temp_zip = Config.UPLOADS_DIR / f"temp_restore_{secrets.token_hex(4)}.zip"
        restore_file.save(str(temp_zip))
        BackupService.restore_backup(temp_zip)
        temp_zip.unlink(missing_ok=True)

        flash("Backup restored successfully!", "success")
        log_audit("RESTORE_BACKUP", "Restored database and media assets from zip backup")
    except Exception as e:
        flash(f"Failed to restore backup: {e}", "danger")

    return redirect(url_for("system.backup"))

@system_bp.route("/users")
@login_required
def users():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    users_list = User.query.order_by(User.created_at.desc()).all()
    return render_template("system/users.html", current_school=school, all_schools=all_schools, users=users_list)

@system_bp.route("/audit")
@login_required
def audit():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    page = int(request.args.get("page", 1))
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("system/audit.html", current_school=school, all_schools=all_schools, logs=pagination.items, pagination=pagination)
