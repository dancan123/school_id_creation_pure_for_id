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
        return "N/A"
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", str(dob_str).strip())
    if m:
        year, month, day = m.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return str(dob_str).strip()

with app.app_context():
    school = School.query.first()
    student = Student.query.filter_by(admission_number='00101').first() or Student.query.first()

    # Let's render Option A: Side-by-side D.O.B and GENDER on row 2
    # Base front card
    img_a = CardRenderer.render_front(school, student)
    
    # Let's inspect where info block is drawn in services/card_renderer.py
    print(f"Loaded student {student.full_name}, DOB: {student.dob}, Gender: {student.gender}")
