import io
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import datetime
from app import create_app
from extensions import db
from models import School, Student, CardRecord
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = create_app()

with app.app_context():
    school = School.query.first()
    print("Testing school:", school.name)
    students = Student.query.filter_by(school_id=school.id, is_archived=False).all()
    print("Total students:", len(students))
    
    # 1. Test Excel Export
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Register"
    ws.views.sheetView[0].showGridLines = True
    
    # Title
    ws.merge_cells("A1:Q1")
    title_cell = ws["A1"]
    title_cell.value = f"{school.name.upper()} - OFFICIAL STUDENT REGISTER"
    title_cell.font = Font(name="Segoe UI", size=15, bold=True, color="1E3A8A")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    ws.merge_cells("A2:Q2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Academic Year: {school.academic_year} | Export Date: {datetime.date.today().strftime('%B %d, %Y')} | Total Registered: {len(students)}"
    sub_cell.font = Font(name="Segoe UI", size=10, italic=True, color="475569")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    headers = [
        "#", "Admission No", "Full Name", "Class / Grade", "Stream", "Curriculum",
        "Gender", "Date of Birth", "UPI / NEMIS", "Parent / Guardian", "Emergency Contact",
        "Blood Group", "House / Dorm", "Card Status", "Card Number", "Card Expiry", "Photo Uploaded"
    ]
    
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws.row_dimensions[4].height = 26
    for col_num, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=col_num, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=9)

    for i, s in enumerate(students, 1):
        row_num = 4 + i
        ws.row_dimensions[row_num].height = 20
        row_data = [
            i,
            s.admission_number,
            s.full_name,
            s.class_name,
            s.stream_name or "-",
            s.curriculum_type or "CBC",
            s.gender or "-",
            s.dob or "-",
            s.nemis_upi or "-",
            s.parent_name or "-",
            s.parent_phone or "-",
            s.blood_group or "-",
            s.house_or_dorm or "-",
            (s.card_status or "pending").capitalize(),
            s.card_number or "-",
            s.expiry_date.strftime("%Y-%m-%d") if s.expiry_date else "-",
            "Yes" if s.photo_filename else "No"
        ]
        is_even = (i % 2 == 0)
        for col_num, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=val)
            cell.font = regular_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill
            if col_num in [1, 2, 4, 5, 6, 7, 8, 12, 14, 16, 17]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row > 2 and cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_size = len(excel_buffer.getvalue())
    print(f"Excel generated successfully! Size: {excel_size} bytes")

    # 2. Test ReportLab PDF Export
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor(school.primary_color or "#1E3A8A"),
        alignment=1 # Center
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        alignment=1 # Center
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5
    )
    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=table_cell_style,
        alignment=1
    )
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )

    story = []
    story.append(Paragraph(f"<b>{school.name.upper()}</b>", title_style))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<b>OFFICIAL STUDENT IDENTIFICATION ROSTER & REGISTER</b><br/>Academic Year: {school.academic_year} &bull; Generated: {datetime.date.today().strftime('%d %B %Y')} &bull; Total Students: {len(students)}", meta_style))
    story.append(Spacer(1, 4 * mm))

    pdf_headers = ["#", "Adm No", "Full Name", "Class", "Stream", "Gender", "UPI / NEMIS", "Emergency Phone", "Card Status", "Card Number", "Photo"]
    data = [[Paragraph(h, header_style) for h in pdf_headers]]

    for idx, s in enumerate(students, 1):
        status_color = "#16A34A" if s.card_status == "active" else ("#D97706" if s.card_status == "pending" else "#64748B")
        photo_text = "<font color='#16A34A'><b>Yes</b></font>" if s.photo_filename else "<font color='#DC2626'><b>No</b></font>"
        status_text = f"<font color='{status_color}'><b>{(s.card_status or 'Pending').capitalize()}</b></font>"
        
        row = [
            Paragraph(str(idx), table_cell_center),
            Paragraph(f"<b>{s.admission_number}</b>", table_cell_center),
            Paragraph(s.full_name[:24], table_cell_style),
            Paragraph(s.class_name, table_cell_center),
            Paragraph(s.stream_name or "-", table_cell_center),
            Paragraph(s.gender or "-", table_cell_center),
            Paragraph(s.nemis_upi or "-", table_cell_center),
            Paragraph(s.parent_phone or "-", table_cell_center),
            Paragraph(status_text, table_cell_center),
            Paragraph(s.card_number or "-", table_cell_center),
            Paragraph(photo_text, table_cell_center),
        ]
        data.append(row)

    col_widths = [10*mm, 20*mm, 52*mm, 20*mm, 18*mm, 16*mm, 28*mm, 30*mm, 24*mm, 28*mm, 17*mm]
    
    t = Table(data, colWidths=col_widths, repeatRows=1)
    primary_c = colors.HexColor(school.primary_color or "#1E3A8A")
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_c),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t)
    
    doc.build(story)
    pdf_size = len(pdf_buffer.getvalue())
    print(f"PDF generated successfully! Size: {pdf_size} bytes")
