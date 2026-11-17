import io
import datetime
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class InvoiceGenerator:
    """Generates KRA-compliant electronic tax invoices & official M-Pesa receipts in PDF."""

    @staticmethod
    def generate_receipt_pdf(transaction, school):
        """Builds a formal PDF receipt for an M-Pesa or wire quota top-up."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm
        )

        styles = getSampleStyleSheet()

        # Custom Typography Styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold"
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#64748B"),
            fontName="Helvetica"
        )
        header_meta_style = ParagraphStyle(
            "HeaderMeta",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            alignment=2 # Right aligned
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading3"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#1E3A8A"),
            fontName="Helvetica-Bold"
        )
        body_text = ParagraphStyle(
            "BodySmall",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1E293B"),
            fontName="Helvetica"
        )
        bold_text = ParagraphStyle(
            "BoldSmall",
            parent=body_text,
            fontName="Helvetica-Bold"
        )

        elements = []

        # ── 1. Header: Platform Identity & Invoice Meta ──────────────────────
        date_eat = (transaction.completed_at or transaction.created_at or datetime.datetime.utcnow()) + datetime.timedelta(hours=3)
        date_str = date_eat.strftime("%d %B %Y, %H:%M:%S EAT")
        receipt_no = f"EDUK-RCP-{date_eat.year}-{transaction.id:05d}"

        header_data = [
            [
                Paragraph("<b>EduID Kenya Credential Systems</b><br/>"
                          "<font size='8' color='#64748B'>Universal Multi-Tenant Identity &amp; Access Infrastructure<br/>"
                          "Republic of Kenya &bull; Support: +254 746 908674 &bull; dancanmbaabu1@gmail.com</font>", title_style),
                Paragraph(f"<b>ELECTRONIC TAX RECEIPT</b><br/>"
                          f"Receipt No: <font color='#1E3A8A'><b>{receipt_no}</b></font><br/>"
                          f"Date: {date_str}<br/>"
                          f"Status: <font color='#059669'><b>PAID IN FULL</b></font>", header_meta_style)
            ]
        ]
        header_table = Table(header_data, colWidths=[105 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 4 * mm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=5 * mm))

        # ── 2. Bill To & Payment Mode Matrix ─────────────────────────────────
        bill_to_content = (
            f"<b>{school.name}</b><br/>"
            f"Institution Code: <font color='#1E3A8A'><b>{school.code or f'ID-{school.id}'}</b></font><br/>"
            f"Type: {(school.institution_type or 'School').capitalize()}<br/>"
            f"County: {school.county or 'Kenya'} County<br/>"
            f"Phone: {school.phone or 'N/A'} &bull; Email: {school.email or 'N/A'}"
        )
        payment_mode_content = (
            f"Payment Method: <b>Safaricom M-Pesa Express</b><br/>"
            f"M-Pesa Receipt: <font color='#059669'><b>{transaction.mpesa_receipt_number or transaction.reference_id[:12].upper()}</b></font><br/>"
            f"Mobile Number: <b>{transaction.phone_number}</b><br/>"
            f"System Trace ID: <font size='7' color='#64748B'>{transaction.reference_id}</font><br/>"
            f"Verification: <b>Automated Daraja Callback</b>"
        )

        details_data = [
            [
                Paragraph("<b>BILLED TO (INSTITUTION)</b>", section_heading),
                Paragraph("<b>PAYMENT CONFIRMATION</b>", section_heading)
            ],
            [
                Paragraph(bill_to_content, body_text),
                Paragraph(payment_mode_content, body_text)
            ]
        ]
        details_table = Table(details_data, colWidths=[90 * mm, 90 * mm])
        details_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 6 * mm))

        # ── 3. Line Items Table ──────────────────────────────────────────────
        gross_amount = float(transaction.amount or 0.0)
        # 16% Kenyan VAT calculations (VAT inclusive)
        net_amount = gross_amount / 1.16
        vat_amount = gross_amount - net_amount

        cards_desc = "Unlimited (Infinite Cards)" if transaction.cards_credited == 0 else f"{transaction.cards_credited:,} ID Cards"

        items_data = [
            [
                Paragraph("<b>Item Description</b>", bold_text),
                Paragraph("<b>Tier</b>", bold_text),
                Paragraph("<b>Allocation</b>", bold_text),
                Paragraph("<b>Amount (KES)</b>", bold_text)
            ],
            [
                Paragraph(f"<b>EduID ID Card Generation Quota Top-Up</b><br/>"
                          f"<font size='8' color='#64748B'>Official high-resolution 300 DPI CR80 card generation allowance for {school.name}. "
                          f"Includes digital verification QR codes and secure cloud storage.</font>", body_text),
                Paragraph((transaction.tier_allocated or "Standard").capitalize(), body_text),
                Paragraph(cards_desc, bold_text),
                Paragraph(f"{gross_amount:,.2f}", bold_text)
            ],
            ["", "", Paragraph("<b>Subtotal (Exc. VAT):</b>", body_text), Paragraph(f"KES {net_amount:,.2f}", body_text)],
            ["", "", Paragraph("<b>VAT (16% Standard Rate):</b>", body_text), Paragraph(f"KES {vat_amount:,.2f}", body_text)],
            ["", "", Paragraph("<b>TOTAL AMOUNT PAID:</b>", bold_text), Paragraph(f"<b>KES {gross_amount:,.2f}</b>", bold_text)]
        ]

        items_table = Table(items_data, colWidths=[80 * mm, 25 * mm, 40 * mm, 35 * mm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, 1), 0.5, colors.HexColor("#CBD5E1")),
            ('LINEBELOW', (2, 2), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('BACKGROUND', (2, 4), (-1, 4), colors.HexColor("#ECFDF5")), # highlight total
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 8 * mm))

        # ── 4. Official Seal Banner & Verification Hash ─────────────────────
        sha_sig = hashlib.sha256(f"{transaction.reference_id}_{transaction.amount}_{school.id}".encode("utf-8")).hexdigest()

        seal_data = [
            [
                Paragraph(f"<font color='#059669'><b>&#10004; OFFICIAL ELECTRONIC PAYMENT CERTIFICATE</b></font><br/>"
                          f"<font size='7.5' color='#475569'>This document serves as an authentic receipt of payment acknowledged by Safaricom Daraja M-Pesa Services.<br/>"
                          f"SHA-256 Digital Verification Hash: <font face='Courier'>{sha_sig[:40]}...</font></font>", body_text)
            ]
        ]
        seal_table = Table(seal_data, colWidths=[180 * mm])
        seal_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#86EFAC")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(seal_table)
        elements.append(Spacer(1, 5 * mm))

        # ── 5. Terms / Footer ────────────────────────────────────────────────
        footer_text = (
            "<font size='7.5' color='#94A3B8'>"
            "1. All card quota allocations are credited immediately and remain active for the validity period of your subscription.<br/>"
            "2. For billing inquiries, tax exemptions, or custom bulk enterprise invoicing, contact billing@eduid.ke or call +254 746 908674.<br/>"
            "EduID Kenya Credential Systems &bull; Powered by Antigravity Cloud &bull; Republic of Kenya"
            "</font>"
        )
        elements.append(Paragraph(footer_text, body_text))

        doc.build(elements)
        buf.seek(0)
        return buf.getvalue()
