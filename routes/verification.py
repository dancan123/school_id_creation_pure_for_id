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
