from flask import Blueprint, render_template, request, flash, Response
from services.qr_service import QRService
from extensions import db
from models import QRVerificationToken, School
from utils import build_public_url

verification_bp = Blueprint("verification", __name__)

@verification_bp.route("/verify/qr/<token>")
@verification_bp.route("/verify/qr/<token>.png")
def qr_code_image(token):
    """Dynamic offline endpoint returning high-contrast, scanner-ready QR code PNG."""
    verification_token = QRVerificationToken.query.filter_by(token=token).first()
    school = db.session.get(School, verification_token.school_id) if verification_token else None
    base_url = build_public_url("", school) if school else request.host_url
    verify_url = f"{base_url.rstrip('/')}/verify/{token}"
    png_bytes = QRService.generate_qr_png_bytes(verify_url, size_px=260, add_shield=True)
    return Response(png_bytes, mimetype="image/png")

@verification_bp.route("/verify/<token>")
def verify_card(token):
    """Public verification endpoint triggered by scanning the card's QR code."""
    result = QRService.verify_token(token)
    return render_template("verification/verify.html", token=token, result=result)

@verification_bp.route("/pass/<token>")
@verification_bp.route("/digital-pass/<token>")
def digital_pass(token):
    """Mobile-first secure digital credential pass with live anti-tamper watermark."""
    result = QRService.verify_token(token)
    return render_template("verification/digital_pass.html", token=token, result=result)

@verification_bp.route("/verify", methods=["GET", "POST"])
def manual_verify():
    """Manual token entry page for security personnel or administration."""
    result = None
    token = None
    if request.method == "POST":
        token = request.form.get("token", "").strip()
        if token:
            result = QRService.verify_token(token)
        else:
            flash("Please enter a verification token.", "warning")

    return render_template("verification/verify.html", token=token, result=result, is_manual=True)

@verification_bp.route("/scanner")
@verification_bp.route("/scanner/<school_code>")
def guard_scanner_portal(school_code=None):
    """Direct mobile QR scanner for security guards, turnstiles, and gate personnel."""
    from flask_login import current_user
    from utils import get_current_school
    school = None
    if school_code:
        school = School.query.filter((School.code == school_code) | (School.name == school_code)).first()
    elif current_user and current_user.is_authenticated:
        school = get_current_school()
    return render_template("verification/guard_scanner.html", school=school)
