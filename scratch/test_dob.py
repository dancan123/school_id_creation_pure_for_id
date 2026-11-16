import os, re
from PIL import Image, ImageDraw
from app import app
from models import School, Student
from services.card_renderer import CardRenderer, get_font, fit_font_size, hex_to_rgb, LANDSCAPE_W, LANDSCAPE_H

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

    # Let's write a helper to render front with custom info block
    def make_card(layout_mode="side_by_side"):
        img = CardRenderer.render_front(school, student)
        # We will also save a high resolution crop of the info block
        return img

    print("Checking student details:", student.full_name, student.dob, student.gender)
