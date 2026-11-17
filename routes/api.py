import os
import hashlib
import datetime
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import current_user, login_required
from extensions import db
from models import School, Student, CardRecord, QRVerificationToken, ApiKey, PaymentTransaction
from services.qr_service import QRService
from services.mpesa_service import MpesaService, PACKAGES
from services.photo_enhancer import PhotoEnhancer
from utils import get_current_school, log_audit

api_bp = Blueprint("api_v1", __name__)

def verify_api_key_header():
    """Optional validation helper for physical turnstile / IoT gate hardware."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    key_hash = hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()
    key_rec = ApiKey.query.filter_by(key_hash=key_hash, is_active=True).first()
    if key_rec:
        key_rec.last_used_at = datetime.datetime.utcnow()
        db.session.commit()
        return key_rec
    return False

# ── 1. Physical Turnstile & Gate Access Control Verification API ─────────────
@api_bp.route("/verify-credential", methods=["POST"])
def verify_credential_api():
    """High-speed JSON verification endpoint for physical access control gates,
    turnstiles, RFID/NFC bridges, and security guard mobile devices.
    """
    key_check = verify_api_key_header()
    if key_check is False:
        return jsonify({"authorized": False, "status": "error", "error": "Invalid API Key"}), 401

    payload = request.get_json(silent=True) or {}
    token = payload.get("token") or payload.get("qr_content") or request.form.get("token")
    if not token:
        return jsonify({"authorized": False, "status": "error", "error": "Token is required."}), 400

    token = token.strip()
    if "/verify/" in token:
        token = token.split("/verify/")[-1].split("?")[0].strip()

    result = QRService.verify_token(token)
    if not result.get("valid"):
        return jsonify({
            "authorized": False,
            "status": result.get("reason", "invalid"),
            "message": result.get("message", "Credential not recognized or revoked."),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }), 200

    student = result.get("student")
    school = result.get("school")
    card = result.get("card")

    # If turnstile API key is present, attribute scan to the specific gate device
    if key_check and result.get("scan_log_id"):
        try:
            from models import GateScanLog
            sl = db.session.get(GateScanLog, result["scan_log_id"])
            if sl:
                sl.api_key_id = key_check.id
                sl.gate_device = key_check.name
                db.session.commit()
        except Exception:
            pass

    # If turnstile API key is scoped to a specific school, enforce tenant boundary
    if key_check and school and key_check.school_id != school.id:
        return jsonify({
            "authorized": False,
            "status": "wrong_institution",
            "message": f"Credential belongs to '{school.name}' but gate is configured for tenant #{key_check.school_id}.",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }), 403

    return jsonify({
        "authorized": True,
        "status": "active",
        "card_title": result.get("card_title"),
        "card_number": card.card_number if card else result.get("card_number", "N/A"),
        "institution": {
            "id": school.id if school else None,
            "name": school.name if school else result.get("school_name"),
            "code": school.code if school else result.get("school_code"),
            "logo_url": f"/media/logos/{school.logo_filename}" if school and school.logo_filename else None,
            "primary_color": school.primary_color if school else "#1E3A8A"
        },
        "member": {
            "id": student.id if student else None,
            "id_number": student.admission_number if student else result.get("admission_number"),
            "id_label": result.get("id_label", "ADM NO"),
            "full_name": student.full_name if student else result.get("student_name"),
            "role": (student.stream_name or student.class_name) if student else result.get("stream_name"),
            "role_label": result.get("stream_label", "STREAM"),
            "department": student.class_name if student else result.get("class_name"),
            "department_label": result.get("class_label", "CLASS"),
            "card_status": ((student.card_status if student else result.get("status")) or "active").upper(),
            "photo_url": f"/media/photos/{student.photo_filename}" if student and student.photo_filename else None
        },
        "scan_count": result.get("scan_count", 1),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200


# ── 2. M-Pesa Daraja Automated STK Push Billing API ──────────────────────────
@api_bp.route("/billing/packages", methods=["GET"])
def get_billing_packages():
    """Lists available self-service card allowance top-up packages."""
    return jsonify({
        "status": "success",
        "packages": MpesaService.get_packages()
    })

@api_bp.route("/billing/mpesa-stk-push", methods=["POST"])
@login_required
def initiate_mpesa_stk_push():
    """Triggers an M-Pesa STK push for the active institution tenant."""
    school = get_current_school()
    if not school:
        return jsonify({"status": "error", "message": "No active institution."}), 400

    data = request.get_json(silent=True) or request.form
    phone = data.get("phone_number")
    package_key = data.get("package_key")

    if not phone or not package_key:
        return jsonify({"status": "error", "message": "phone_number and package_key are required."}), 400

    try:
        res = MpesaService.initiate_stk_push(
            school=school,
            user=current_user,
            phone_number=phone,
            package_key=package_key
        )
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@api_bp.route("/billing/mpesa-callback", methods=["POST"])
def mpesa_daraja_callback():
    """Webhook invoked by Safaricom Daraja upon completion or failure of STK push."""
    payload = request.get_json(silent=True) or {}
    res = MpesaService.process_callback(payload)
    return jsonify(res), 200

@api_bp.route("/billing/status/<int:transaction_id>", methods=["GET"])
def check_payment_status(transaction_id):
    """Polling endpoint for UI to monitor payment transaction progress in real-time."""
    txn = PaymentTransaction.query.get(transaction_id)
    if not txn:
        return jsonify({"status": "not_found"}), 404

    sch = txn.school
    return jsonify({
        "status": txn.status,
        "transaction_id": txn.id,
        "reference_id": txn.reference_id,
        "package_name": txn.package_name,
        "cards_credited": txn.cards_credited,
        "amount": txn.amount,
        "mpesa_receipt": txn.mpesa_receipt_number,
        "school": {
            "id": sch.id if sch else None,
            "name": sch.name if sch else None,
            "max_cards_quota": sch.max_cards_quota if sch else None,
            "remaining_quota": sch.get_remaining_quota() if sch else None,
            "tier": sch.subscription_tier if sch else None
        }
    })

@api_bp.route("/billing/simulate-success/<int:transaction_id>", methods=["POST"])
def simulate_mpesa_success(transaction_id):
    """Allows instant confirmation for testing / developer mode without waiting for live Daraja PIN."""
    txn = PaymentTransaction.query.get(transaction_id)
    if not txn:
        return jsonify({"status": "error", "message": "Transaction not found"}), 404

    if txn.status == "completed":
        return jsonify({"status": "already_completed", "message": "Transaction already credited."})

    receipt = request.form.get("receipt_number") or f"SIM-{hashlib.md5(str(transaction_id).encode()).hexdigest()[:8].upper()}"
    MpesaService.apply_successful_payment(txn, receipt, "Simulated instant test payment")
    return jsonify({
        "status": "completed",
        "receipt_number": receipt,
        "message": f"Successfully credited {txn.cards_credited} cards to {txn.school.name}."
    })


@api_bp.route("/billing/receipt/<int:transaction_id>.pdf", methods=["GET"])
def download_tax_receipt(transaction_id):
    """Generates an official KRA-compliant electronic tax invoice & payment receipt PDF."""
    txn = db.session.get(PaymentTransaction, transaction_id)
    if not txn:
        return Response("Transaction not found", status=404, mimetype="text/plain")

    school = txn.school or db.session.get(School, txn.school_id)
    if not school:
        return Response("Associated institution not found", status=404, mimetype="text/plain")

    from services.invoice_generator import InvoiceGenerator
    pdf_bytes = InvoiceGenerator.generate_receipt_pdf(txn, school)
    safe_rec = txn.mpesa_receipt_number or txn.reference_id[:8]
    filename = f"EduID_Tax_Receipt_{school.code or school.id}_{safe_rec}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


# ── 3. AI / Smart Photo Auto-Center & Passport Normalizer API ─────────────────
@api_bp.route("/photos/enhance", methods=["POST"])
@login_required
def enhance_photo_api():
    """Accepts an uploaded passport photo and applies automated headshot centering,
    3:4 aspect ratio normalization, and contrast enhancement.
    """
    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "Photo file is required."}), 400

    try:
        raw_bytes = file.read()
        enhanced_bytes = PhotoEnhancer.enhance_passport_photo(raw_bytes, target_size=(480, 640))
        import base64
        b64_str = base64.b64encode(enhanced_bytes).decode("utf-8")
        return jsonify({
            "status": "success",
            "message": "Photo centered and standardized to CR80 3:4 passport ratio.",
            "data_url": f"data:image/jpeg;base64,{b64_str}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# ── 4. Mobile Security Guard QR Scanner View ─────────────────────────────────
@api_bp.route("/scanner", methods=["GET"])
@api_bp.route("/scanner/<school_code>", methods=["GET"])
def mobile_guard_scanner(school_code=None):
    """Full-screen interactive mobile QR scanner designed for security guards at gates.
    Plays instant audio chime on scan, verifies credentials via JSON API, and displays
    high-contrast access status.
    """
    school = None
    if school_code:
        school = School.query.filter((School.code == school_code) | (School.name == school_code)).first()
    elif current_user and current_user.is_authenticated:
        school = get_current_school()

    return render_template("verification/guard_scanner.html", school=school)
