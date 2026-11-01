import secrets
from pathlib import Path
from flask import session, request, current_app
from flask_login import current_user
from extensions import db
from models import School, AuditLog

def build_public_url(path, school=None):
    """Build a canonical public link, preferring school/system URL settings."""
    base_url = (getattr(school, "onboarding_base_url", None) or
                current_app.config.get("PUBLIC_BASE_URL") or
                request.host_url).strip().rstrip("/")
    return f"{base_url}/{path.lstrip('/')}"

def get_current_school():
    """Returns currently selected School in session or first available school, creating one if empty."""
    school_id = session.get("active_school_id")
    if school_id:
        school = db.session.get(School, school_id)
        if school:
            return school

    # Fallback to first school
    school = School.query.filter_by(is_active=True).first()
    if school:
        session["active_school_id"] = school.id
        return school

    # If no school exists in the system at all, create a standard default school
    default_school = School(
        name="Alliance High School",
        code="AHS-001",
        motto="Strong to Serve",
        po_box="P.O. Box 7 - 00902",
        town="Kikuyu",
        county="Kiambu",
        phone="+254 722 000111",
        email="info@alliancehigh.ac.ke",
        website="https://alliancehigh.ac.ke",
        primary_color="#1E3A8A",   # Royal Navy Blue
        secondary_color="#F59E0B", # Gold
        accent_color="#10B981",    # Emerald
        card_bg_color="#FFFFFF",
        text_color="#0F172A",
        principal_name="Principal / Chief Principal",
        academic_year="2026",
        card_prefix="AHS-",
        validity_years=4
    )
    db.session.add(default_school)
    db.session.commit()
    session["active_school_id"] = default_school.id
    return default_school

def log_audit(action, details=None, school_id=None):
    """Records an audit log entry for system actions."""
    try:
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        username = current_user.username if current_user and current_user.is_authenticated else "System"
        ip = request.remote_addr if request else "127.0.0.1"

        if not school_id and current_user and hasattr(current_user, "school_id") and current_user.school_id:
            school_id = current_user.school_id
        elif not school_id:
            school_id = session.get("active_school_id")

        log = AuditLog(
            school_id=school_id,
            user_id=user_id,
            username=username,
            action=action,
            details=details,
            ip_address=ip
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Failed to record audit log: {e}")

def save_uploaded_file(file_storage, target_dir, prefix="file_"):
    """Saves an uploaded file with a secure unique filename and returns the filename."""
    if not file_storage or not file_storage.filename:
        return None
    ext = Path(file_storage.filename).suffix.lower()
    unique_fn = f"{prefix}{secrets.token_hex(8)}{ext}"
    target_path = Path(target_dir) / unique_fn
    file_storage.save(str(target_path))
    return unique_fn

def save_base64_image(base64_data, target_dir, prefix="img_", default_ext=".jpg"):
    """Decodes a base64 Data URL or raw base64 string, saves to target_dir with unique filename."""
    if not base64_data or not isinstance(base64_data, str) or len(base64_data) < 20:
        return None
    try:
        import base64
        ext = default_ext
        if "data:image/png" in base64_data:
            ext = ".png"
        elif "data:image/jpeg" in base64_data or "data:image/jpg" in base64_data:
            ext = ".jpg"
        elif "data:image/webp" in base64_data:
            ext = ".webp"
        
        if "," in base64_data:
            _, encoded = base64_data.split(",", 1)
        else:
            encoded = base64_data
            
        raw_bytes = base64.b64decode(encoded)
        unique_fn = f"{prefix}{secrets.token_hex(8)}{ext}"
        target_path = Path(target_dir) / unique_fn
        with open(target_path, "wb") as f:
            f.write(raw_bytes)
        return unique_fn
    except Exception as e:
        print(f"Failed to save base64 image: {e}")
        return None

def clean_kenyan_phone_for_whatsapp(phone):
    """
    Sanitizes Kenyan and international phone numbers for wa.me links.
    Converts 0712345678 or 0112345678 -> 254712345678 or 254112345678.
    """
    if not phone:
        return None
    # Remove all non-digits except initial plus
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return None
    
    # Standard Kenyan mobile formats
    if digits.startswith("0") and len(digits) == 10:
        return "254" + digits[1:]
    if digits.startswith("254") and len(digits) == 12:
        return digits
    if (digits.startswith("7") or digits.startswith("1")) and len(digits) == 9:
        return "254" + digits
    
    return digits if len(digits) >= 9 else None

def build_whatsapp_link(phone=None, message=""):
    """
    Builds an official https://wa.me/ universal link.
    Works seamlessly on WhatsApp Web, WhatsApp Desktop, and mobile apps.
    """
    import urllib.parse
    clean_phone = clean_kenyan_phone_for_whatsapp(phone) if phone else None
    encoded = urllib.parse.quote(message) if message else ""
    
    if clean_phone:
        return f"https://wa.me/{clean_phone}" + (f"?text={encoded}" if encoded else "")
    return "https://wa.me/" + (f"?text={encoded}" if encoded else "")

def get_whatsapp_onboarding_share_url(school, onboard_url):
    """Generates standard WhatsApp broadcast invitation for school student onboarding."""
    school_name = school.name if school else "School"
    motto = f'"{school.motto}"' if school and school.motto else ""
    code = (school.code or school.id) if school else ""
    year = school.academic_year if school else "2026"
    
    msg = (
        f"🏫 *{school_name}*\n"
        f"{motto}\n\n"
        f"📢 *STUDENT ID CARD REGISTRATION & ONBOARDING*\n"
        f"Dear Parents and Students,\n"
        f"Please complete student registration and upload your passport photo online using our official portal:\n\n"
        f"🔗 {onboard_url}\n\n"
        f"📌 *School Code:* {code}\n"
        f"📅 *Academic Year:* {year}\n\n"
        f"_Powered by EduID Kenya System_"
    )
    return build_whatsapp_link(phone=None, message=msg)

def get_whatsapp_parent_card_notice_url(student, school, card=None, tracking_url=None):
    """Generates WhatsApp message link directly to a student's parent/guardian."""
    parent_phone = student.parent_phone or (student.emergency_phone if hasattr(student, "emergency_phone") else None)
    school_name = school.name if school else "School"
    card_no = card.card_number if card else (student.card_number or "N/A")
    
    msg = (
        f"🎓 *{school_name} — Student ID Card Ready*\n"
        f"Dear Parent / Guardian of *{student.full_name}*,\n\n"
        f"We are pleased to inform you that the official Student Identification Card has been produced.\n\n"
        f"• *Student Name:* {student.full_name}\n"
        f"• *Admission No:* {student.admission_number}\n"
        f"• *Class:* {student.class_name} {student.stream_name or ''}\n"
        f"• *Card Number:* {card_no}\n\n"
        f"📍 *Collection:* Please visit the school administration office to collect the physical card.\n"
        f"Thank you!"
    )
    return build_whatsapp_link(phone=parent_phone, message=msg)


