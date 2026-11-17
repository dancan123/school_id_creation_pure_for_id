import io
import secrets
import datetime
import qrcode
from PIL import Image, ImageDraw  # type: ignore
from extensions import db
from models import QRVerificationToken, CardRecord, Student, School, GateScanLog

class QRService:
    @staticmethod
    def generate_unique_token():
        """Generates a secure 32-character random hex token."""
        return secrets.token_hex(16)

    @staticmethod
    def generate_qr_image(data_url, size_px=240, add_shield=True):
        """Generates a high-contrast, ISO/IEC 18004 compliant QR code PIL Image.

        Features:
        - ERROR_CORRECT_H (30% error recovery): Ensures flawless scanning even on
          worn/scratched PVC cards, laminated plastic glare, and camera tilt.
        - Strict ISO standard 4-module quiet zone (border=4).
        - Pure binary contrast (#000000 on #FFFFFF) optimized for dye-sublimation K-resin ribbon.
        - Optional micro central security shield badge (occupies <3.5% total area).
        - Resampled with NEAREST to preserve razor-sharp pixel module edges.
        """
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data_url)
        qr.make(fit=True)

        base_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
        w, h = base_img.size

        if add_shield:
            # Shield covers <3.5% area, perfectly safe for Level H (30% tolerance)
            shield_size = int(w * 0.17)
            sx = (w - shield_size) // 2
            sy = (h - shield_size) // 2

            draw = ImageDraw.Draw(base_img)
            # White protective disc with sharp black border
            draw.ellipse(
                [sx - 3, sy - 3, sx + shield_size + 3, sy + shield_size + 3],
                fill=(255, 255, 255),
                outline=(0, 0, 0),
                width=3
            )

            cx = sx + shield_size // 2
            cy = sy + shield_size // 2
            pad = int(shield_size * 0.22)
            top = sy + pad
            bot = sy + shield_size - pad
            left = sx + pad
            right = sx + shield_size - pad
            mid_y = top + int((bot - top) * 0.55)

            shield_pts = [
                (left, top),
                (right, top),
                (right, mid_y),
                (cx, bot),
                (left, mid_y),
            ]
            draw.polygon(shield_pts, fill=(15, 23, 42))

            # Inner high-contrast checkmark
            check_pts = [
                (cx - 7, cy),
                (cx - 2, cy + 5),
                (cx + 8, cy - 6),
            ]
            draw.line(check_pts, fill=(255, 255, 255), width=3)

        if size_px and (w != size_px or h != size_px):
            base_img = base_img.resize((size_px, size_px), Image.Resampling.NEAREST)

        return base_img

    @staticmethod
    def generate_qr_png_bytes(data_url, size_px=240, add_shield=True):
        """Generates raw PNG bytes for HTTP response."""
        img = QRService.generate_qr_image(data_url, size_px=size_px, add_shield=add_shield)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def create_token_for_card(school_id, student_id, card_record_id):
        token_str = QRService.generate_unique_token()
        token = QRVerificationToken(
            token=token_str,
            school_id=school_id,
            student_id=student_id,
            card_record_id=card_record_id,
            is_valid=True,
            scan_count=0,
            last_scanned_at=None
        )
        db.session.add(token)
        return token_str

    @staticmethod
    def verify_token(token_str):
        """Looks up verification record and increments scan counter safely."""
        token_entry = QRVerificationToken.query.filter_by(token=token_str).first()
        if not token_entry:
            card_alt = CardRecord.query.filter_by(qr_token=token_str).first()
            if card_alt:
                token_entry = QRVerificationToken(
                    token=token_str,
                    school_id=card_alt.school_id,
                    student_id=card_alt.student_id,
                    card_record_id=card_alt.id,
                    is_valid=True,
                    scan_count=0
                )
                db.session.add(token_entry)
                db.session.commit()
            else:
                return {"valid": False, "message": "Invalid or unrecognized verification token."}

        token_entry.scan_count += 1
        token_entry.last_scanned_at = datetime.datetime.utcnow()
        db.session.commit()

        student = db.session.get(Student, token_entry.student_id)
        school = db.session.get(School, token_entry.school_id)
        card = db.session.get(CardRecord, token_entry.card_record_id) if token_entry.card_record_id else None

        if not student or not school:
            return {"valid": False, "message": "Associated student or school record not found."}

        # Check validity & expiry
        is_active = (card.status == "active") if card else (student.card_status == "active")
        is_expired = False
        if card and card.expiry_date and card.expiry_date < datetime.date.today():
            is_expired = True
            is_active = False

        status_text = "ACTIVE & AUTHENTIC" if (is_active and not is_expired) else ("EXPIRED" if is_expired else "INACTIVE / REVOKED")

        # Automatically record gate entry scan for security analytics & attendance
        scan_record_id = None
        try:
            scan_status = "granted" if (is_active and not is_expired) else ("expired" if is_expired else "denied")
            scan_entry = GateScanLog(
                school_id=school.id,
                student_id=student.id,
                card_record_id=card.id if card else None,
                token=token_str,
                member_name=student.full_name,
                admission_number=student.admission_number,
                department=student.class_name,
                role_title=student.stream_name or student.class_name,
                photo_filename=student.photo_cropped_filename or student.photo_filename,
                scan_status=scan_status,
                gate_device="Mobile Gate Scanner",
                scanned_at=datetime.datetime.utcnow()
            )
            db.session.add(scan_entry)
            db.session.commit()
            scan_record_id = scan_entry.id
        except Exception:
            db.session.rollback()

        return {
            "valid": is_active and not is_expired,
            "status_text": status_text,
            "status": card.status if card else student.card_status,
            "scan_log_id": scan_record_id,
            "student_name": student.full_name,
            "admission_number": student.admission_number,
            "class_name": student.class_name,
            "stream_name": student.stream_name or "N/A",
            "academic_year": student.academic_year,
            "school_name": school.name,
            "school_code": school.code or f"ID-{school.id}",
            "school_county": school.county,
            "school_phone": school.phone,
            "school_logo": school.logo_filename,
            "primary_color": school.primary_color or "#1E3A8A",
            "institution_type": school.institution_type or "school",
            "card_title": school.get_card_title() if hasattr(school, "get_card_title") else "IDENTITY CARD",
            "id_label": school.get_id_label() if hasattr(school, "get_id_label") else "ID NO",
            "member_label": school.get_member_label() if hasattr(school, "get_member_label") else "Member",
            "class_label": school.get_class_label() if hasattr(school, "get_class_label") else "Department / Unit",
            "stream_label": school.get_stream_label() if hasattr(school, "get_stream_label") else "Job Title / Role",
            "card_number": card.card_number if card else "N/A",
            "issue_date": str(card.issue_date) if card and card.issue_date else "N/A",
            "expiry_date": str(card.expiry_date) if card and card.expiry_date else "N/A",
            "scan_count": token_entry.scan_count,
            "last_scanned": token_entry.last_scanned_at.strftime("%Y-%m-%d %H:%M:%S UTC") if token_entry.last_scanned_at else "First scan",
            "student": student,
            "school": school,
            "card": card
        }
