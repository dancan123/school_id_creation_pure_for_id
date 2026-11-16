import os, re
from PIL import Image, ImageDraw
from app import app
from models import School, Student
from services.card_renderer import (
    CardRenderer, get_font, fit_font_size, hex_to_rgb,
    LANDSCAPE_W, LANDSCAPE_H
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
    student = Student.query.filter_by(admission_number='00101').first() or Student.query.first()
    
    w, h = LANDSCAPE_W, LANDSCAPE_H
    pri_rgb = hex_to_rgb(school.primary_color)
    text_rgb = (30, 41, 59)
    lbl_font = get_font(20, bold=True)
    val_font = get_font(24, bold=True)
    
    photo_x = 40
    photo_w = int(w * 0.28)
    info_x = photo_x + photo_w + 92
    col2_x = info_x + 175
    avail_val_w = (w - 35) - col2_x

    # Render Layout 1: Side by side on row below NAME
    # NAME: FAITH WANJIKU KARIUKI
    # D.O.B: 18/02/2011    GENDER: FEMALE
    # ADM NO: 00101
    # CLASS / GRADE: Form 1 North
    # CARD NO: ID-00101
    # EXPIRES: DEC 2029
    img1 = CardRenderer.render_front(school, student)
    d1 = ImageDraw.Draw(img1)
    
    # Render Layout 2: Two separate rows
    # NAME: FAITH WANJIKU KARIUKI
    # D.O.B: 18/02/2011
    # GENDER: FEMALE
    # ADM NO: 00101
    # ...
    
    print("Script ready")
