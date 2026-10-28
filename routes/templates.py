import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import School, IdTemplate
from utils import get_current_school, log_audit

templates_bp = Blueprint("templates_designer", __name__)

PRESET_THEMES = [
    {
        "id": "classic_royal",
        "name": "Classic Royal (Navy & Gold)",
        "description": "Prestigious Kenyan national and county school color scheme.",
        "primary": "#1E3A8A",
        "secondary": "#F59E0B",
        "accent": "#10B981",
        "text": "#0F172A"
    },
    {
        "id": "emerald_crest",
        "name": "Emerald Crest (Forest Green & Amber)",
        "description": "Rich traditional academic green with warm amber accents.",
        "primary": "#065F46",
        "secondary": "#D97706",
        "accent": "#FBBF24",
        "text": "#0F172A"
    },
    {
        "id": "maroon_elite",
        "name": "Maroon Elite (Crimson Maroon & Gold)",
        "description": "Distinguished maroon with gold trims and crisp white background.",
        "primary": "#881337",
        "secondary": "#F59E0B",
        "accent": "#38BDF8",
        "text": "#0F172A"
    },
    {
        "id": "modern_tech",
        "name": "Modern Academy (Deep Slate & Cyan)",
        "description": "Modern technical high school and academy appearance.",
        "primary": "#0F172A",
        "secondary": "#0284C7",
        "accent": "#38BDF8",
        "text": "#0F172A"
    },
    {
        "id": "highland_purple",
        "name": "Highland Majesty (Royal Purple & Gold)",
        "description": "Vibrant royal purple paired with brilliant sunshine gold.",
        "primary": "#581C87",
        "secondary": "#F59E0B",
        "accent": "#10B981",
        "text": "#0F172A"
    }
]

@templates_bp.route("/")
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    templates = IdTemplate.query.filter((IdTemplate.school_id == school.id) | (IdTemplate.school_id == None)).all()
    return render_template(
        "templates_designer/index.html",
        current_school=school,
        all_schools=all_schools,
        templates=templates,
        presets=PRESET_THEMES
    )

@templates_bp.route("/apply-preset/<preset_id>", methods=["POST"])
@login_required
def apply_preset(preset_id):
    school = get_current_school()
    preset = next((p for p in PRESET_THEMES if p["id"] == preset_id), None)
    if preset:
        school.primary_color = preset["primary"]
        school.secondary_color = preset["secondary"]
        school.accent_color = preset["accent"]
        school.text_color = preset["text"]
        db.session.commit()
        flash(f"Applied '{preset['name']}' color scheme to {school.name}!", "success")
        log_audit("APPLY_THEME_PRESET", f"Applied {preset['name']} to {school.name}")
    else:
        flash("Preset not found.", "warning")

    return redirect(url_for("templates_designer.index"))
