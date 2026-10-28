import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import School, Student, CardRecord
from utils import get_current_school, log_audit

print_queue_bp = Blueprint("print_queue", __name__)

@print_queue_bp.route("/")
@login_required
def index():
    school = get_current_school()
    all_schools = School.query.filter_by(is_active=True).all()

    status_filter = request.args.get("status", "all")
    class_filter = request.args.get("class", "").strip()
    page = int(request.args.get("page", 1))

    query = CardRecord.query.filter_by(school_id=school.id)

    if status_filter != "all":
        query = query.filter_by(print_status=status_filter)

    if class_filter:
        query = query.join(Student).filter(Student.class_name == class_filter)

    # Distinct classes
    classes = [r[0] for r in db.session.query(Student.class_name).filter_by(school_id=school.id, is_archived=False).distinct().order_by(Student.class_name).all()]

    pagination = query.order_by(CardRecord.created_at.desc()).paginate(page=page, per_page=30, error_out=False)

    pending_count = CardRecord.query.filter_by(school_id=school.id, print_status="pending").count()
    printed_count = CardRecord.query.filter_by(school_id=school.id, print_status="printed").count()

    return render_template(
        "print_queue/index.html",
        current_school=school,
        all_schools=all_schools,
        cards=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        class_filter=class_filter,
        classes=classes,
        pending_count=pending_count,
        printed_count=printed_count
    )

@print_queue_bp.route("/mark-printed/<int:card_id>", methods=["POST"])
@login_required
def mark_card_printed(card_id):
    school = get_current_school()
    card = CardRecord.query.filter_by(id=card_id, school_id=school.id).first_or_404()
    card.print_status = "printed"
    card.printed_at = datetime.datetime.utcnow()
    card.print_count = (card.print_count or 0) + 1
    db.session.commit()
    flash(f"Card {card.card_number} marked as printed.", "success")
    log_audit("MARK_CARD_PRINTED", f"Marked card {card.card_number} as printed")
    return redirect(request.referrer or url_for("print_queue.index"))

@print_queue_bp.route("/mark-all-printed", methods=["POST"])
@login_required
def mark_all_printed():
    school = get_current_school()
    pending_cards = CardRecord.query.filter_by(school_id=school.id, print_status="pending").all()
    now = datetime.datetime.utcnow()
    for c in pending_cards:
        c.print_status = "printed"
        c.printed_at = now
        c.print_count = (c.print_count or 0) + 1

    db.session.commit()
    flash(f"All {len(pending_cards)} pending cards marked as printed.", "success")
    log_audit("MARK_ALL_PRINTED", f"Marked {len(pending_cards)} cards as printed")
    return redirect(url_for("print_queue.index"))
