from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from extensions import db
from models import School
from config import Config
from utils import get_current_school, log_audit, save_uploaded_file

schools_bp = Blueprint("schools", __name__)

@schools_bp.route("/switch/<int:school_id>")
@login_required
def switch_school(school_id):
    school = School.query.get_or_404(school_id)
    session["active_school_id"] = school.id
    flash(f"Switched active school to: {school.name}", "success")
    log_audit("SWITCH_SCHOOL", f"Switched to school ID {school.id} ({school.name})")
    # Redirect back to referring page or dashboard
    return redirect(request.referrer or url_for("dashboard.index"))

@schools_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_school():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip() or None
        motto = request.form.get("motto", "").strip()
        town = request.form.get("town", "Nairobi").strip()
        county = request.form.get("county", "Nairobi").strip()
        po_box = request.form.get("po_box", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        
        # Colors
        primary_color = request.form.get("primary_color", "#1E3A8A")
        secondary_color = request.form.get("secondary_color", "#F59E0B")
        accent_color = request.form.get("accent_color", "#10B981")

        card_prefix = request.form.get("card_prefix", "ID-").strip()
        academic_year = request.form.get("academic_year", "2026").strip()
        validity_years = int(request.form.get("validity_years", 4))

        if not name:
            flash("School Name is required.", "danger")
            return redirect(url_for("schools.create_school"))

        if School.query.filter_by(name=name).first():
            flash(f"A school named '{name}' already exists.", "danger")
            return redirect(url_for("schools.create_school"))

        # Institution type & Corporate Fields
        institution_type = request.form.get("institution_type", "school").strip()
        card_title = request.form.get("card_title", "").strip()
        id_label = request.form.get("id_label", "").strip()
        class_label = request.form.get("class_label", "").strip()
        stream_label = request.form.get("stream_label", "").strip()
        upi_label = request.form.get("upi_label", "").strip()
        principal_name = request.form.get("principal_name", "").strip()
        principal_title = request.form.get("principal_title", "").strip()

        # Corporate / Company intelligent presets if empty
        is_corp = institution_type in ["company", "corporate", "enterprise", "business", "organization", "ngo"]
        if is_corp:
            if not card_prefix or card_prefix == "ID-":
                card_prefix = "EMP-"
            if not card_title:
                card_title = "STAFF IDENTIFICATION CARD"
            if not id_label:
                id_label = "STAFF NO"
            if not class_label:
                class_label = "DEPARTMENT"
            if not stream_label:
                stream_label = "JOB TITLE"
            if not upi_label:
                upi_label = "NATIONAL ID"
            if not principal_title:
                principal_title = "Managing Director"

        new_school = School(
            name=name,
            code=code,
            motto=motto,
            town=town,
            county=county,
            po_box=po_box,
            phone=phone,
            email=email,
            institution_type=institution_type,
            card_title=card_title,
            id_label=id_label,
            class_label=class_label,
            stream_label=stream_label,
            upi_label=upi_label,
            principal_name=principal_name,
            principal_title=principal_title,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            card_prefix=card_prefix,
            academic_year=academic_year,
            validity_years=validity_years
        )

        # Handle Logo
        if "logo_file" in request.files:
            logo_f = request.files["logo_file"]
            if logo_f and logo_f.filename:
                fn = save_uploaded_file(logo_f, Config.LOGOS_DIR, prefix="logo_")
                new_school.logo_filename = fn

        db.session.add(new_school)
        db.session.commit()

        session["active_school_id"] = new_school.id
        flash(f"School '{new_school.name}' registered successfully! It is now the active school.", "success")
        log_audit("CREATE_SCHOOL", f"Registered school: {new_school.name}")
        return redirect(url_for("schools.settings"))

    all_schools = School.query.filter_by(is_active=True).all()
    current_school = get_current_school()
    return render_template("schools/new.html", all_schools=all_schools, current_school=current_school)

@schools_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    if request.method == "POST":
        school.name = request.form.get("name", school.name).strip()
        school.code = request.form.get("code", school.code).strip() or None
        school.motto = request.form.get("motto", school.motto).strip()
        school.po_box = request.form.get("po_box", school.po_box).strip()
        school.town = request.form.get("town", school.town).strip()
        school.county = request.form.get("county", school.county).strip()
        school.phone = request.form.get("phone", school.phone).strip()
        school.email = request.form.get("email", school.email).strip()
        school.website = request.form.get("website", school.website).strip()
        
        # Color adjustments
        school.primary_color = request.form.get("primary_color", school.primary_color)
        school.secondary_color = request.form.get("secondary_color", school.secondary_color)
        school.accent_color = request.form.get("accent_color", school.accent_color)
        school.text_color = request.form.get("text_color", school.text_color)

        school.principal_name = request.form.get("principal_name", school.principal_name).strip()
        school.card_prefix = request.form.get("card_prefix", school.card_prefix).strip()
        school.academic_year = request.form.get("academic_year", school.academic_year).strip()
        school.validity_years = int(request.form.get("validity_years", school.validity_years))
        school.disclaimer_text = request.form.get("disclaimer_text", school.disclaimer_text).strip()
        school.emergency_contact_phone = request.form.get("emergency_contact_phone", "").strip()
        school.allow_self_onboarding = request.form.get("allow_self_onboarding") == "1"
        school.auto_approve_onboarding = request.form.get("auto_approve_onboarding") == "1"
        school.onboarding_instructions = request.form.get("onboarding_instructions", "").strip()

        # ── Institution / Corporate settings ─────────────────────────────
        school.institution_type = request.form.get("institution_type", school.institution_type or "school").strip()
        school.principal_title = request.form.get("principal_title", school.principal_title or "").strip()
        school.card_title = request.form.get("card_title", school.card_title or "").strip()
        school.id_label = request.form.get("id_label", school.id_label or "").strip()
        school.class_label = request.form.get("class_label", school.class_label or "").strip()
        school.stream_label = request.form.get("stream_label", school.stream_label or "").strip()
        school.upi_label = request.form.get("upi_label", school.upi_label or "").strip()
        school.enable_watermark = request.form.get("enable_watermark") == "1"

        # Handle Logo upload
        if "logo_file" in request.files:
            logo_f = request.files["logo_file"]
            if logo_f and logo_f.filename:
                fn = save_uploaded_file(logo_f, Config.LOGOS_DIR, prefix="logo_")
                school.logo_filename = fn

        # Handle Signature upload
        if "signature_file" in request.files:
            sig_f = request.files["signature_file"]
            if sig_f and sig_f.filename:
                fn = save_uploaded_file(sig_f, Config.SIGNATURES_DIR, prefix="sig_")
                school.principal_signature_filename = fn

        # Handle Official Stamp upload
        if "stamp_file" in request.files:
            stamp_f = request.files["stamp_file"]
            if stamp_f and stamp_f.filename:
                fn = save_uploaded_file(stamp_f, Config.STAMPS_DIR, prefix="stamp_")
                school.stamp_filename = fn

        db.session.commit()
        flash(f"Settings for '{school.name}' updated successfully!", "success")
        log_audit("UPDATE_SCHOOL_SETTINGS", f"Updated settings for {school.name}")
        return redirect(url_for("schools.settings"))

    return render_template("schools/settings.html", current_school=school, all_schools=all_schools)
