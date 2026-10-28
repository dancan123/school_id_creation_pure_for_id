import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, School

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    # If no users exist, create default admin user
    if User.query.count() == 0:
        admin = User(
            username="admin",
            email="admin@schoolidsystem.ke",
            full_name="System Administrator",
            role="superadmin",
            is_active=True
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        flash("Initial system administrator created (Username: admin, Password: admin123). Please log in.", "info")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash("Your account has been deactivated. Please contact administrator.", "danger")
                return render_template("auth/login.html")

            login_user(user)
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()

            # Set active school if user belongs to one or pick first school
            if user.school_id:
                session["active_school_id"] = user.school_id
            else:
                first_school = School.query.filter_by(is_active=True).first()
                if first_school:
                    session["active_school_id"] = first_school.id

            flash(f"Welcome back, {user.full_name}!", "success")
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("active_school_id", None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))
