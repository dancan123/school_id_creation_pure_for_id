import datetime
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, School, AuditLog
from utils import log_audit, find_institution_by_code_or_id

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if getattr(current_user, "is_platform_admin", False) or current_user.role == "superadmin":
            return redirect(url_for("superadmin.index"))
        return redirect(url_for("dashboard.index"))

    # Resolve scoped institution if code is passed
    inst_param = (
        request.args.get("code") or
        request.args.get("institution") or
        request.args.get("school_code") or
        request.form.get("institution_code", "")
    ).strip()
    scoped_school = find_institution_by_code_or_id(inst_param) if inst_param else None

    # If no users exist, create default superadmin user
    if User.query.count() == 0:
        admin = User(
            username="admin",
            email="admin@schoolidsystem.ke",
            full_name="Platform Super Administrator",
            role="superadmin",
            is_platform_admin=True,
            is_active=True
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        flash("Initial platform administrator created (Username: admin, Password: admin123). Please log in.", "info")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter((User.username == username) | (User.email == username)).first()

        # Brute force check
        now = datetime.datetime.utcnow()
        if user and user.locked_until and user.locked_until > now:
            minutes_left = int((user.locked_until - now).total_seconds() / 60) + 1
            flash(f"Account is temporarily locked due to repeated failed logins. Please try again in {minutes_left} minute(s).", "danger")
            return render_template("auth/login.html", scoped_school=scoped_school)

        if user and user.check_password(password):
            # Reset failed attempts on success
            user.failed_login_attempts = 0
            user.locked_until = None

            # Multi-Tenant Workspace Boundary Check:
            # If logging in at a scoped institution page, only users belonging to that institution
            # or platform super administrators are permitted.
            if scoped_school and not (getattr(user, "is_platform_admin", False) or user.role == "superadmin"):
                if user.school_id != scoped_school.id:
                    flash(f"Access Denied: Account '{username}' belongs to another institution and cannot access {scoped_school.name}. Please log in at your assigned workspace.", "danger")
                    log_audit("CROSS_TENANT_LOGIN_BLOCKED", f"User {username} attempted login at {scoped_school.name} (Code: {scoped_school.code})", school_id=scoped_school.id)
                    return render_template("auth/login.html", scoped_school=scoped_school)

            if not user.is_active:
                # Check if it's tied to an unapproved institution
                if user.school_id:
                    sch = db.session.get(School, user.school_id)
                    if sch and sch.status == "pending":
                        flash("Your institution registration is pending Super Admin review. You will be activated upon approval.", "warning")
                        return redirect(url_for("auth.registration_status", school_id=sch.id))
                    elif sch and sch.status == "suspended":
                        flash("Your institution account has been suspended. Please contact platform support.", "danger")
                        return redirect(url_for("auth.tenant_suspended"))
                flash("Your account has been deactivated. Please contact your administrator.", "danger")
                return render_template("auth/login.html", scoped_school=scoped_school)

            # Check tenant status if user belongs to a school
            if user.school_id and not (getattr(user, "is_platform_admin", False) or user.role == "superadmin"):
                sch = db.session.get(School, user.school_id)
                if sch:
                    if sch.status == "pending":
                        flash("Your institution application is pending Super Admin approval.", "warning")
                        return redirect(url_for("auth.registration_status", school_id=sch.id))
                    elif sch.status == "suspended":
                        flash("Your institution's account has been suspended. Please contact platform support.", "danger")
                        return redirect(url_for("auth.tenant_suspended"))
                    elif sch.status == "inactive" or not sch.is_active:
                        flash("Your institution's account is currently inactive.", "danger")
                        return redirect(url_for("auth.tenant_suspended"))

            login_user(user)
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()

            # Set active school context
            if user.school_id:
                session["active_school_id"] = user.school_id
            elif scoped_school:
                session["active_school_id"] = scoped_school.id
            else:
                first_school = School.query.filter_by(is_active=True).first()
                if first_school:
                    session["active_school_id"] = first_school.id

            log_audit("USER_LOGIN", f"User {user.username} logged in successfully", school_id=user.school_id)
            flash(f"Welcome back, {user.full_name}!", "success")

            # Superadmin direct to superadmin dashboard
            if getattr(user, "is_platform_admin", False) or user.role == "superadmin":
                return redirect(url_for("superadmin.index"))

            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))
        else:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = now + datetime.timedelta(minutes=15)
                    log_audit("ACCOUNT_LOCKED", f"User {user.username} locked after 5 failed attempts")
                    flash("Account locked for 15 minutes due to 5 consecutive failed login attempts.", "danger")
                else:
                    flash(f"Invalid username or password. ({5 - user.failed_login_attempts} attempts remaining)", "danger")
                db.session.commit()
            else:
                flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", scoped_school=scoped_school)

@auth_bp.route("/logout")
@login_required
def logout():
    log_audit("USER_LOGOUT", f"User {current_user.username} logged out")
    logout_user()
    session.pop("active_school_id", None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register-institution", methods=["GET", "POST"])
def register_institution():
    """Public self-service institution onboarding portal."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        org_name = request.form.get("org_name", "").strip()
        org_type = request.form.get("org_type", "school").strip()
        registration_no = request.form.get("registration_number", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip().lower()
        contact_phone = request.form.get("contact_phone", "").strip()
        county = request.form.get("county", "Nairobi").strip()
        town = request.form.get("town", "Nairobi").strip()
        po_box = request.form.get("po_box", "").strip()
        physical_address = request.form.get("physical_address", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Validation
        if not org_name or not contact_name or not contact_email or not contact_phone or not username or not password:
            flash("All required fields must be filled.", "danger")
            return render_template("auth/register_institution.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("auth/register_institution.html")

        if School.query.filter_by(name=org_name).first():
            flash(f"An institution named '{org_name}' is already registered or pending review.", "danger")
            return render_template("auth/register_institution.html")

        if User.query.filter((User.username == username) | (User.email == contact_email)).first():
            flash("The administrator username or email address is already in use.", "danger")
            return render_template("auth/register_institution.html")

        # Generate institution code from initials + random hex
        initials = "".join([w[0] for w in org_name.split() if w])[:4].upper() or "ORG"
        code = f"{initials}-{secrets.token_hex(2).upper()}"

        # Setup presets based on institution type
        is_corp = org_type in ["company", "corporate", "enterprise", "business", "organization", "ngo"]
        card_prefix = "EMP-" if is_corp else ("REG-" if org_type in ["university", "tvet"] else "ID-")
        card_title = "STAFF IDENTIFICATION CARD" if is_corp else ("UNIVERSITY IDENTIFICATION CARD" if org_type == "university" else "STUDENT IDENTIFICATION CARD")
        id_label = "STAFF NO" if is_corp else ("REG NO" if org_type in ["university", "tvet"] else "ADM NO")
        class_label = "DEPARTMENT" if is_corp else ("FACULTY / DEPT" if org_type == "university" else "CLASS / GRADE")
        stream_label = "ROLE / DESIGNATION" if is_corp else ("COURSE / PROGRAMME" if org_type == "university" else "STREAM")

        new_school = School(
            name=org_name,
            code=code,
            institution_type=org_type,
            registration_number=registration_no,
            contact_person_name=contact_name,
            contact_person_phone=contact_phone,
            phone=contact_phone,
            email=contact_email,
            county=county,
            town=town,
            po_box=po_box,
            physical_address=physical_address,
            card_prefix=card_prefix,
            card_title=card_title,
            id_label=id_label,
            class_label=class_label,
            stream_label=stream_label,
            status="active",
            subscription_tier="free_trial",
            max_cards_quota=2,
            cards_generated_count=0,
            is_active=True
        )
        db.session.add(new_school)
        db.session.flush()

        # Create tenant owner user - immediately active on Free Trial (2 cards)
        owner_user = User(
            username=username,
            email=contact_email,
            full_name=contact_name,
            phone_number=contact_phone,
            role="org_owner",
            school_id=new_school.id,
            is_platform_admin=False,
            is_active=True
        )
        owner_user.set_password(password)
        db.session.add(owner_user)
        db.session.commit()

        log_audit(
            "INSTITUTION_REGISTERED_TRIAL",
            f"Institution '{org_name}' registered on Free Trial (Quota: 2 cards) by {contact_name} ({username})",
            school_id=new_school.id
        )

        flash(f"Welcome to EduID Kenya! Your workspace for '{org_name}' is ready with 2 Free Trial ID Cards. Please log in to begin.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register_institution.html")

@auth_bp.route("/registration-status/<int:school_id>")
def registration_status(school_id):
    """Displays registration status and onboarding checklist for applicants."""
    school = db.session.get(School, school_id)
    if not school:
        flash("Institution record not found.", "danger")
        return redirect(url_for("auth.login"))
    owner = User.query.filter_by(school_id=school.id, role="org_owner").first()
    return render_template("auth/registration_status.html", school=school, owner=owner)

@auth_bp.route("/tenant-suspended")
def tenant_suspended():
    """Notice page for suspended or deactivated institutions."""
    return render_template("auth/tenant_suspended.html")
