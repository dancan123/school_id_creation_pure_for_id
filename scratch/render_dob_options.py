import os, re
from PIL import Image, ImageDraw
from app import app
from models import School, Student
from services.card_renderer import (
    CardRenderer, get_font, fit_font_size, hex_to_rgb,
    LANDSCAPE_W, LANDSCAPE_H, draw_guilloche_watermark,
    draw_smart_chip, clean_logo_image, clean_ink_signature, Config
)

def format_dob(dob_str):
    if not dob_str:
        return ""
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", str(dob_str).strip())
    if m:
        year, month, day = m.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return str(dob_str).strip()

with app.app_context():
    school = School.query.first()
    student = Student.query.filter_by(admission_number='00101').first()
    if not student:
        student = Student.query.first()

    pri_rgb = hex_to_rgb(school.primary_color)
    sec_rgb = hex_to_rgb(school.secondary_color)
    acc_rgb = (250, 204, 21)
    text_rgb = (30, 41, 59)
    w, h = LANDSCAPE_W, LANDSCAPE_H

    # Test Layout 1: Side-by-side (D.O.B: 18/02/2011    GENDER: FEMALE)
    img1 = CardRenderer.render_front(school, student)
    # We can inspect base img1, but let's draw on a copy
    # Let's inspect coordinates in img1
    
    # Let's render a custom front for Option 1 (Side-by-side)
    # and Option 2 (Two separate lines)
    print("Testing render options...")
