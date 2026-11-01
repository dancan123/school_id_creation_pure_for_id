import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, Response
from flask_login import login_required
from extensions import db
from models import Student, School, CardRecord, IdTemplate
from config import Config
from utils import get_current_school, log_audit, build_public_url
from services.card_renderer import CardRenderer

single_id_bp = Blueprint("single_id", __name__)


# ── Live Card Preview Image Endpoints ─────────────────────────────────────────
@single_id_bp.route("/preview/front/<int:student_id>")
@login_required
def preview_front(student_id):
    """Renders the front of the ID card in-memory and returns it as a PNG.
    This ensures the browser preview is pixel-for-pixel identical to the PDF."""
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    card = CardRecord.query.filter_by(student_id=student.id, status="active").first()
    try:
        img = CardRenderer.render_front(school, student, card)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        buf.seek(0)
        return Response(buf.read(), mimetype="image/png",
                        headers={"Cache-Control": "no-store, max-age=0"})
    except Exception as exc:
        return Response(f"Preview error: {exc}", status=500, mimetype="text/plain")


@single_id_bp.route("/preview/back/<int:student_id>")
@login_required
def preview_back(student_id):
    """Renders the back of the ID card in-memory and returns it as a PNG."""
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    card = CardRecord.query.filter_by(student_id=student.id, status="active").first()
    base_url = build_public_url("", school).rstrip("/")
    try:
        img = CardRenderer.render_back(school, student, card, verify_base_url=base_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        buf.seek(0)
        return Response(buf.read(), mimetype="image/png",
                        headers={"Cache-Control": "no-store, max-age=0"})
    except Exception as exc:
        return Response(f"Preview error: {exc}", status=500, mimetype="text/plain")


# ─────────────────────────────────────────────────────────────────────────────


@single_id_bp.route("/", methods=["GET"])
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()
    students = Student.query.filter_by(school_id=school.id, is_archived=False).order_by(Student.full_name).all()
    templates = IdTemplate.query.filter((IdTemplate.school_id == school.id) | (IdTemplate.school_id == None)).all()

    student_id = request.args.get("student_id")
    selected_student = Student.query.filter_by(id=student_id, school_id=school.id).first() if student_id else None

    existing_card = None
    card_history = []
    if selected_student:
        existing_card = CardRecord.query.filter_by(student_id=selected_student.id, status="active").first()
        card_history = CardRecord.query.filter_by(student_id=selected_student.id).order_by(CardRecord.created_at.desc()).limit(8).all()

    return render_template(
        "single_id/generate.html",
        current_school=school,
        all_schools=all_schools,
        students=students,
        templates=templates,
        selected_student=selected_student,
        existing_card=existing_card,
        card_history=card_history
    )

@single_id_bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate_card():
    school = get_current_school()
    if request.method == "GET":
        # Older/shared links used /generate?student_id=... . Do not mutate state
        # on GET; send the user to the card preview, where generation is explicit.
        student_id = request.args.get("student_id", type=int)
        if not student_id or not Student.query.filter_by(id=student_id, school_id=school.id).first():
            flash("Select a student to preview or generate an ID card.", "warning")
            return redirect(url_for("single_id.index"))
        flash("Review the card preview, then select Generate ID Card to create or refresh it.", "info")
        return redirect(url_for("single_id.index", student_id=student_id))

    student_id = request.form.get("student_id")
    template_id = request.form.get("template_id") or None
    is_reprint = request.form.get("is_reprint") == "1"
    reprint_reason = request.form.get("reprint_reason", "").strip()

    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()

    # Look for existing active card
    existing_card = CardRecord.query.filter_by(student_id=student.id, status="active").first()

    if existing_card and is_reprint:
        existing_card.status = "replaced"
        existing_card.reprint_reason = reprint_reason or "Card Replacement"
        db.session.commit()

    base_url = build_public_url("", school).rstrip("/")
    card = CardRenderer.generate_card_for_student(school, student, base_url, template_id=template_id)

    flash(f"ID Card for {student.full_name} ({student.admission_number}) generated successfully!", "success")
    log_audit("GENERATE_SINGLE_ID", f"Generated ID for student {student.admission_number} ({card.card_number})")

    return redirect(url_for("single_id.index", student_id=student.id))


@single_id_bp.route("/renew/<int:student_id>", methods=["POST"])
@login_required
def renew_card(student_id):
    """Renews a single student's ID card, archiving the old one."""
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    renewal_notes = request.form.get("renewal_notes", "").strip()

    base_url = build_public_url("", school).rstrip("/")
    card = CardRenderer.renew_card_for_student(school, student, base_url, renewal_notes=renewal_notes)

    flash(f"ID Card renewed for {student.full_name} ({student.admission_number}). New expiry: {card.expiry_date}", "success")
    log_audit("RENEW_SINGLE_ID", f"Renewed ID for student {student.admission_number} → new card {card.card_number} (R{card.renewal_count})")
    return redirect(url_for("single_id.index", student_id=student.id))


@single_id_bp.route("/renew-bulk", methods=["POST"])
@login_required
def renew_bulk():
    """Bulk renews cards for a subset or all students - by class, stream, or explicit IDs."""
    school = get_current_school()
    scope = request.form.get("scope", "selected")  # 'selected', 'class', 'stream', 'all'
    class_filter = request.form.get("class_name", "").strip()
    stream_filter = request.form.get("stream_name", "").strip()
    student_ids_raw = request.form.getlist("student_ids")
    renewal_notes = request.form.get("renewal_notes", "").strip()

    query = Student.query.filter_by(school_id=school.id, is_archived=False)
    if scope == "class" and class_filter:
        query = query.filter(Student.class_name == class_filter)
        if stream_filter:
            query = query.filter(Student.stream_name == stream_filter)
    elif scope == "selected" and student_ids_raw:
        ids = [int(i) for i in student_ids_raw if i.isdigit()]
        query = query.filter(Student.id.in_(ids))

    students = query.all()
    if not students:
        flash("No students matched the criteria for bulk renewal.", "warning")
        return redirect(url_for("single_id.index"))

    base_url = build_public_url("", school).rstrip("/")
    renewed = 0
    failed = 0
    for student in students:
        try:
            CardRenderer.renew_card_for_student(school, student, base_url, renewal_notes=renewal_notes)
            renewed += 1
        except Exception:
            failed += 1

    flash(f"Bulk Renewal Complete: {renewed} cards renewed" + (f", {failed} failed." if failed else "."), "success")
    log_audit("BULK_RENEW_IDS", f"Bulk renewed {renewed} cards for {school.name} (scope={scope})")
    return redirect(url_for("bulk_generate.index"))


@single_id_bp.route("/history/<int:student_id>")
@login_required
def card_history(student_id):
    """API endpoint returning card history for a student as JSON."""
    school = get_current_school()
    student = Student.query.filter_by(id=student_id, school_id=school.id).first_or_404()
    cards = CardRecord.query.filter_by(student_id=student.id).order_by(CardRecord.created_at.desc()).all()
    return jsonify([{
        "id": c.id,
        "card_number": c.card_number,
        "status": c.status,
        "issue_date": str(c.issue_date),
        "expiry_date": str(c.expiry_date),
        "print_count": c.print_count,
        "renewal_count": c.renewal_count or 0,
        "renewal_notes": c.renewal_notes or "",
        "has_pdf": bool(c.single_pdf_filename),
        "download_url": url_for("single_id.download_card_pdf", card_id=c.id, _external=False)
    } for c in cards])


@single_id_bp.route("/download/<int:card_id>")
@login_required
def download_card_pdf(card_id):
    school = get_current_school()
    card = CardRecord.query.filter_by(id=card_id, school_id=school.id).first_or_404()

    # Re-generate card images and PDF so the downloaded file ALWAYS reflects
    # the latest template styling, signature placement, and terms layout in 100% parity with live preview
    base_url = build_public_url("", school).rstrip("/")
    front_path, back_path = CardRenderer.save_card_images(school, card.student, card, base_url)

    pdf_filename = card.single_pdf_filename or f"card_{school.id}_{card.student.admission_number}_{card.qr_token[:6]}.pdf"
    pdf_path = Config.PDFS_DIR / pdf_filename
    CardRenderer.generate_single_cr80_pdf(front_path, back_path, pdf_path)
    card.single_pdf_filename = pdf_filename

    card.print_count += 1
    db.session.commit()
    log_audit("DOWNLOAD_SINGLE_PDF", f"Downloaded PDF for card {card.card_number}")

    view_mode = request.args.get("view") == "1"
    suffix = f"_R{card.renewal_count}" if (card.renewal_count or 0) > 0 else ""
    return send_file(
        str(pdf_path),
        as_attachment=not view_mode,
        download_name=f"{card.card_number}_{card.student.admission_number}{suffix}_CR80.pdf"
    )
