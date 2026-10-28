import io
import secrets
import datetime
import qrcode
from PIL import Image, ImageDraw
from extensions import db
from models import QRVerificationToken, CardRecord, Student, School

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

        return {
            "valid": is_active and not is_expired,
            "status_text": status_text,
            "status": card.status if card else student.card_status,
            "student_name": student.full_name,
            "admission_number": student.admission_number,
            "class_name": student.class_name,
            "stream_name": student.stream_name or "N/A",
            "academic_year": student.academic_year,
            "school_name": school.name,
            "school_county": school.county,
            "school_phone": school.phone,
            "card_number": card.card_number if card else "N/A",
            "issue_date": str(card.issue_date) if card and card.issue_date else "N/A",
            "expiry_date": str(card.expiry_date) if card and card.expiry_date else "N/A",
            "scan_count": token_entry.scan_count,
            "last_scanned": token_entry.last_scanned_at.strftime("%Y-%m-%d %H:%M:%S UTC") if token_entry.last_scanned_at else "First scan"
        }
