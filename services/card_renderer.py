import os
import io
import math
import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from config import Config

# Standard CR80 Dimensions in mm and 300 DPI pixels
CR80_W_MM = 85.60
CR80_H_MM = 53.98
DPI = 300

# Pixels at 300 DPI
LANDSCAPE_W = int(round((CR80_W_MM / 25.4) * DPI))  # 1011 px
LANDSCAPE_H = int(round((CR80_H_MM / 25.4) * DPI))  # 638 px

PORTRAIT_W = LANDSCAPE_H
PORTRAIT_H = LANDSCAPE_W

def hex_to_rgb(hex_str):
    if not hex_str:
        return (30, 58, 138)
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (30, 58, 138)

def get_font(size, bold=False):
    """Attempt to load a clean system font or fallback to default."""
    font_names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "calibrib.ttf" if bold else "calibri.ttf"
    ]
    # Windows font directories
    win_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    for name in font_names:
        p = win_fonts / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def draw_guilloche_watermark(draw, width, height, pri_rgb):
    """Draws world-class, authentic security guilloche background:
    - Multi-frequency intersecting micro-wave patterns (diamond moiré weave)
    - High-security parametric spirograph rosette medallion
    - Fine concentric security lathe rings
    - Micro-text security banner track
    """
    # 1. Subtle background security tint (ivory-pearl with 2% primary tint)
    r_tint = min(255, int(pri_rgb[0] * 0.08 + 236))
    g_tint = min(255, int(pri_rgb[1] * 0.08 + 238))
    b_tint = min(255, int(pri_rgb[2] * 0.08 + 242))
    line_color_1 = (r_tint, g_tint, b_tint)

    r_tint2 = min(255, int(pri_rgb[0] * 0.12 + 224))
    g_tint2 = min(255, int(pri_rgb[1] * 0.12 + 226))
    b_tint2 = min(255, int(pri_rgb[2] * 0.12 + 232))
    line_color_2 = (r_tint2, g_tint2, b_tint2)

    # 2. Intersecting Diamond Moiré Micro-Waves (Opposing Phase Harmonics)
    step = 22
    for y in range(85, height - 60, step):
        pts1 = []
        pts2 = []
        for x in range(0, width + 10, 12):
            off1 = (math.sin(x / 42.0 + y / 28.0) * 5.5 +
                    math.cos(x / 18.0) * 2.5 +
                    math.sin(x / 75.0) * 3.0)
            pts1.append((x, y + off1))
            off2 = (math.sin(x / 42.0 - y / 28.0 + math.pi) * 5.5 +
                    math.cos(x / 18.0 + math.pi / 2.0) * 2.5 +
                    math.sin(x / 75.0) * 3.0)
            pts2.append((x, y + off2))

        for i in range(len(pts1) - 1):
            draw.line([pts1[i], pts1[i+1]], fill=line_color_1, width=1)
            draw.line([pts2[i], pts2[i+1]], fill=line_color_2, width=1)

    # 3. High-Security Parametric Spirograph Rosette Medallion (Epitrochoid / Hypotrochoid)
    center_rosette_x = int(width * 0.67)
    center_rosette_y = int(height * 0.54)
    
    for radius in (140, 165, 190):
        draw.ellipse([center_rosette_x - radius, center_rosette_y - radius,
                      center_rosette_x + radius, center_rosette_y + radius],
                     outline=line_color_2, width=1)
    
    R = 120.0
    r = 35.0
    d = 45.0
    rosette_pts = []
    num_steps = 360
    for step_i in range(num_steps + 1):
        theta = (step_i / num_steps) * (math.pi * 14)
        rx = center_rosette_x + (R - r) * math.cos(theta) + d * math.cos((R - r) * theta / r)
        ry = center_rosette_y + (R - r) * math.sin(theta) - d * math.sin((R - r) * theta / r)
        rosette_pts.append((rx, ry))

    for i in range(len(rosette_pts) - 1):
        draw.line([rosette_pts[i], rosette_pts[i+1]], fill=line_color_2, width=1)

    r2 = 18.0
    d2 = 28.0
    rosette2_pts = []
    for step_i in range(180 + 1):
        theta = (step_i / 180.0) * (math.pi * 10)
        rx = center_rosette_x + (70.0 - r2) * math.cos(theta) + d2 * math.cos((70.0 - r2) * theta / r2)
        ry = center_rosette_y + (70.0 - r2) * math.sin(theta) - d2 * math.sin((70.0 - r2) * theta / r2)
        rosette2_pts.append((rx, ry))

    for i in range(len(rosette2_pts) - 1):
        draw.line([rosette2_pts[i], rosette2_pts[i+1]], fill=line_color_1, width=1)

    # 4. Micro-text Security Lathe Track along top
    micro_font = get_font(9, bold=True)
    if micro_font:
        micro_str = "★ OFFICIAL SECURE CREDENTIAL ★ REPUBLIC OF KENYA ★ CR80 PVC SMART IDENTITY CORE ★ DIGITAL VERIFICATION EMBEDDED ★ "
        micro_color = (
            min(255, int(pri_rgb[0] * 0.18 + 200)),
            min(255, int(pri_rgb[1] * 0.18 + 200)),
            min(255, int(pri_rgb[2] * 0.18 + 205))
        )
        try:
            draw.text((35, int(height * 0.26) + 20), micro_str[:110], fill=micro_color, font=micro_font)
        except Exception:
            pass

def draw_smart_chip(draw, x, y, w=56, h=44):
    """Draws world-class metallic gold ISO 7816 smart card contact microchip."""
    gold_dark = (180, 115, 6)
    gold_mid = (235, 170, 25)
    gold_light = (254, 240, 138)
    gold_highlight = (255, 251, 235)

    # Outer chip body with chamfered/rounded corners
    draw.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=gold_mid, outline=gold_dark, width=2)
    # Inner subtle bevel
    draw.rounded_rectangle([x + 2, y + 2, x + w - 2, y + h - 2], radius=4, outline=gold_light, width=1)

    # ISO 7816 contact grid pattern
    cx = x + w // 2
    cy = y + h // 2
    # Horizontal divider
    draw.line([x + 6, cy, x + w - 6, cy], fill=gold_dark, width=1)
    # Left vertical divider
    draw.line([x + 18, y + 6, x + 18, y + h - 6], fill=gold_dark, width=1)
    # Right vertical divider
    draw.line([x + w - 18, y + 6, x + w - 18, y + h - 6], fill=gold_dark, width=1)
    # Center grounding pad with gold highlight
    draw.rounded_rectangle([cx - 9, cy - 8, cx + 9, cy + 8], radius=3, fill=gold_light, outline=gold_dark, width=1)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=gold_highlight, outline=gold_dark, width=1)

def get_official_rubber_stamp(school, size=(190, 190), angle=-8):
    """Generates or loads official institution rubber stamp / seal as an RGBA image."""
    # Check if custom stamp image uploaded
    if school.stamp_filename:
        for folder in [Config.STAMPS_DIR, Config.SIGNATURES_DIR, Config.LOGOS_DIR]:
            p = folder / school.stamp_filename
            if p.exists():
                try:
                    stamp_img = Image.open(p).convert("RGBA")
                    stamp_img.thumbnail(size, Image.Resampling.LANCZOS)
                    # Semi-transparent overlay
                    r, g, b, a = stamp_img.split()
                    a = a.point(lambda p: int(p * 0.88))
                    stamp_img.putalpha(a)
                    return stamp_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
                except Exception:
                    pass

    # Vector generated authentic circular double-ring rubber stamp
    w, h = size
    stamp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(stamp)

    pri_rgb = hex_to_rgb(school.primary_color)
    # Stamp ink color: deep official navy-blue derived from primary, semi-transparent
    ink_color = (max(20, min(180, pri_rgb[0])), max(20, min(140, pri_rgb[1])), max(80, min(220, pri_rgb[2])), 210)

    cx, cy = w // 2, h // 2
    r_outer = min(cx, cy) - 6
    r_inner = r_outer - 10
    r_center = r_inner - 22

    # Double concentric outer rings
    sdraw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], outline=ink_color, width=3)
    sdraw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], outline=ink_color, width=2)
    sdraw.ellipse([cx - r_center, cy - r_center, cx + r_center, cy + r_center], outline=ink_color, width=1)

    # Stamp text — always use int coords (PIL ignores float coords on some versions)
    clean_name = school.name.upper()
    if len(clean_name) > 22:
        clean_name = clean_name[:20] + ".."

    name_font = get_font(12, bold=True)
    seal_font = get_font(13, bold=True)
    meta_font = get_font(11, bold=True)

    try:
        # Use integer x-offset; avoid special Unicode chars that may not render
        name_offset_x = int(cx - len(clean_name) * 3.8)
        sdraw.text((name_offset_x, cy - 38), clean_name, fill=ink_color, font=name_font)
        sdraw.text((cx - 54, cy - 12), "** OFFICIAL SEAL **", fill=ink_color, font=seal_font)
        sdraw.text((cx - 42, cy + 10), f"VERIFIED {school.academic_year}", fill=ink_color, font=meta_font)
        sdraw.text((cx - 30, cy + 26), (school.town or "KENYA").upper(), fill=ink_color, font=meta_font)
    except Exception:
        # Ultimate fallback: just draw the ring lines — better than a crash
        pass

    return stamp.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

class CardRenderer:
    """Production-grade Card Renderer producing high-res 300 DPI PNGs and ReportLab print PDFs."""

    @staticmethod
    def render_front(school, student, card_record, template=None):
        """Generates Front ID card PIL Image (1011 x 638 px)."""
        w, h = LANDSCAPE_W, LANDSCAPE_H
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        pri_rgb = hex_to_rgb(school.primary_color)
        sec_rgb = hex_to_rgb(school.secondary_color)
        acc_rgb = hex_to_rgb(school.accent_color)
        text_rgb = hex_to_rgb(school.text_color or "#0F172A")

        # Subtle high-security guilloche watermark background
        if getattr(school, "enable_watermark", True):
            draw_guilloche_watermark(draw, w, h, pri_rgb)

        # Top Header Banner
        header_height = int(h * 0.26)
        draw.rectangle([0, 0, w, header_height], fill=pri_rgb)
        
        # Diagonal / Accent stripe under header
        stripe_h = 14
        draw.rectangle([0, header_height, w, header_height + stripe_h], fill=sec_rgb)
        draw.rectangle([0, header_height + stripe_h, w, header_height + stripe_h + 4], fill=acc_rgb)

        # Bottom Footer Bar
        footer_height = int(h * 0.10)
        draw.rectangle([0, h - footer_height, w, h], fill=pri_rgb)
        draw.rectangle([0, h - footer_height - 6, w, h - footer_height], fill=sec_rgb)

        # School Logo
        logo_drawn = False
        logo_box_w, logo_box_h = int(w * 0.16), int(header_height * 0.85)
        logo_x, logo_y = 25, int((header_height - logo_box_h) / 2)

        if school.logo_filename:
            logo_path = Config.LOGOS_DIR / school.logo_filename
            if logo_path.exists():
                try:
                    logo_img = Image.open(logo_path).convert("RGBA")
                    logo_img.thumbnail((logo_box_w, logo_box_h), Image.Resampling.LANCZOS)
                    img.paste(logo_img, (logo_x, logo_y + (logo_box_h - logo_img.height) // 2), logo_img)
                    logo_drawn = True
                except Exception:
                    logo_drawn = False

        if not logo_drawn:
            draw.ellipse([logo_x, logo_y, logo_x + logo_box_h, logo_y + logo_box_h], fill=sec_rgb, outline=(255,255,255), width=3)
            emblem_font = get_font(32, bold=True)
            first_letters = "".join([part[0] for part in school.name.split()[:2]]).upper()
            draw.text((logo_x + 18, logo_y + 18), first_letters, fill=pri_rgb, font=emblem_font)

        # School Name and details in Header
        text_x = logo_x + logo_box_w + 20
        name_font = get_font(34, bold=True)
        motto_font = get_font(20, bold=False)
        address_font = get_font(18, bold=False)

        school_name = school.name.upper()
        if len(school_name) > 36:
            school_name = school_name[:34] + "..."
        draw.text((text_x, logo_y + 4), school_name, fill=(255, 255, 255), font=name_font)
        
        motto_text = f'"{school.motto}"' if school.motto else ""
        if motto_text:
            draw.text((text_x, logo_y + 45), motto_text, fill=(254, 240, 138), font=motto_font)

        addr_text = f"{school.po_box} • {school.town}, {school.county}"
        draw.text((text_x, logo_y + 75), addr_text, fill=(241, 245, 249), font=address_font)

        # Badge: Dynamic Card Title (STUDENT / CORPORATE ID CARD)
        card_title_str = getattr(school, "get_card_title", lambda: "STUDENT IDENTITY CARD")()
        badge_w = max(240, len(card_title_str) * 11 + 30)
        badge_h = 32
        badge_x = w - badge_w - 25
        badge_y = header_height + stripe_h + 16
        draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=6, fill=pri_rgb)
        badge_font = get_font(15, bold=True)
        draw.text((badge_x + 16, badge_y + 7), card_title_str, fill=(255, 255, 255), font=badge_font)

        # Academic / Year Tag
        year_w, year_h = 120, 32
        year_x = badge_x - year_w - 10
        draw.rounded_rectangle([year_x, badge_y, year_x + year_w, badge_y + year_h], radius=6, fill=sec_rgb)
        year_font = get_font(15, bold=True)
        year_label = f"YR {student.academic_year}" if getattr(school, "is_corporate", lambda: False)() else f"AY {student.academic_year}"
        draw.text((year_x + 16, badge_y + 7), year_label, fill=(15, 23, 42), font=year_font)

        # Renewal Stamp Badge (if card has been renewed)
        if card_record and getattr(card_record, "renewal_count", 0) > 0:
            ren_w, ren_h = 110, 26
            ren_x = year_x - ren_w - 8
            draw.rounded_rectangle([ren_x, badge_y + 3, ren_x + ren_w, badge_y + 3 + ren_h], radius=5, fill=(16, 185, 129))
            ren_font = get_font(12, bold=True)
            draw.text((ren_x + 10, badge_y + 8), f"RENEWED R{card_record.renewal_count}", fill=(255, 255, 255), font=ren_font)

        # Student Photo Frame
        photo_x, photo_y = 40, header_height + stripe_h + 20
        photo_w, photo_h = int(w * 0.28), int(h * 0.51) # ~283 x 325 px

        # Outer luxury double border: metallic gold outer, clean white inner spacer
        draw.rounded_rectangle([photo_x - 3, photo_y - 3, photo_x + photo_w + 3, photo_y + photo_h + 3], radius=8, fill=sec_rgb)
        draw.rounded_rectangle([photo_x - 1, photo_y - 1, photo_x + photo_w + 1, photo_y + photo_h + 1], radius=7, fill=(255, 255, 255))
        draw.rounded_rectangle([photo_x, photo_y, photo_x + photo_w, photo_y + photo_h], radius=6, fill=(240, 244, 248))

        # Paste Photo
        photo_pasted = False
        target_photo_fn = student.photo_cropped_filename or student.photo_filename
        if target_photo_fn:
            photo_path = Config.PHOTOS_DIR / target_photo_fn
            if photo_path.exists():
                try:
                    s_photo = Image.open(photo_path).convert("RGB")
                    s_photo = ImageOps.fit(s_photo, (photo_w, photo_h), Image.Resampling.LANCZOS)
                    img.paste(s_photo, (photo_x, photo_y))
                    photo_pasted = True
                except Exception:
                    photo_pasted = False

        if not photo_pasted:
            draw.rectangle([photo_x, photo_y, photo_x + photo_w, photo_y + photo_h], fill=(226, 232, 240))
            center_x = photo_x + photo_w // 2
            draw.ellipse([center_x - 40, photo_y + 50, center_x + 40, photo_y + 130], fill=(148, 163, 184))
            draw.chord([center_x - 70, photo_y + 140, center_x + 70, photo_y + 260], 180, 360, fill=(148, 163, 184))
            ph_font = get_font(18, bold=True)
            draw.text((photo_x + 35, photo_y + photo_h - 40), "NO PHOTO", fill=(100, 116, 139), font=ph_font)

        # High-security holographic foil shield watermark on photo corner
        holo_x = photo_x + photo_w - 28
        holo_y = photo_y + photo_h - 28
        draw.ellipse([holo_x - 1, holo_y - 1, holo_x + 23, holo_y + 23], fill=sec_rgb)
        draw.ellipse([holo_x, holo_y, holo_x + 22, holo_y + 22], fill=(254, 240, 138), outline=pri_rgb, width=1)
        holo_font = get_font(12, bold=True)
        if holo_font:
            try:
                draw.text((holo_x + 5, holo_y + 3), "★", fill=pri_rgb, font=holo_font)
            except Exception:
                pass

        # Smart Gold Contactless Security Chip beside photo
        draw_smart_chip(draw, photo_x + photo_w + 22, photo_y + 10, w=56, h=44)

        # Information Block with Dynamic Labels and Perfect Harmonized Column Offsets
        info_x = photo_x + photo_w + 92
        start_y = header_height + stripe_h + 58
        line_spacing = 38

        lbl_font = get_font(18, bold=False)
        val_font = get_font(21, bold=True)
        name_val_font = get_font(25, bold=True)

        id_lbl_text = f"{getattr(school, 'get_id_label', lambda: 'ADM NO')()}:"
        class_lbl_text = f"{getattr(school, 'get_class_label', lambda: 'CLASS / GRADE')()}:"

        # Column 2 value start offset (guaranteed 165px label space - never collides)
        col2_x = info_x + 165

        # Full Name with auto font-scaling for longer names
        draw.text((info_x, start_y), "NAME:", fill=(100, 116, 139), font=lbl_font)
        clean_full_name = student.full_name.upper()
        if len(clean_full_name) > 28:
            name_font_to_use = get_font(20, bold=True)
        elif len(clean_full_name) > 22:
            name_font_to_use = get_font(22, bold=True)
        else:
            name_font_to_use = name_val_font
        draw.text((col2_x, start_y - 3), clean_full_name, fill=pri_rgb, font=name_font_to_use)

        # ID / Admission Number
        curr_y = start_y + line_spacing + 4
        draw.text((info_x, curr_y), id_lbl_text, fill=(100, 116, 139), font=lbl_font)
        draw.text((col2_x, curr_y), student.admission_number, fill=text_rgb, font=val_font)

        # Class / Department & Stream (properly spaced in column 2, no overlap)
        curr_y += line_spacing
        draw.text((info_x, curr_y), class_lbl_text, fill=(100, 116, 139), font=lbl_font)
        cls_stream_str = f"{student.class_name} {student.stream_name or ''}".strip()
        draw.text((col2_x, curr_y), cls_stream_str, fill=text_rgb, font=val_font)

        # Card Number
        curr_y += line_spacing
        draw.text((info_x, curr_y), "CARD NO:", fill=(100, 116, 139), font=lbl_font)
        card_no = card_record.card_number if card_record else f"{school.card_prefix or 'ID-'}{student.admission_number}"
        draw.text((col2_x, curr_y), card_no, fill=text_rgb, font=val_font)

        # Valid Until / Expiry
        curr_y += line_spacing
        draw.text((info_x, curr_y), "EXPIRES:", fill=(100, 116, 139), font=lbl_font)
        exp_date_str = str(card_record.expiry_date) if card_record and card_record.expiry_date else f"DEC {int(student.academic_year) + (school.validity_years or 4)}"
        draw.text((col2_x, curr_y), exp_date_str, fill=(220, 38, 38), font=val_font)

        # ── Cardholder Signature Zone ──────────────────────────────────────────
        # Lifted safely above the bottom footer margin (raised by 12px from initial -50)
        # Guarantees a minimum 9px breathing space from the footer accent line
        sig_w = 150
        sig_paste_x = w - sig_w - 28
        sig_paste_y = h - footer_height - 62
        sig_baseline_y = sig_paste_y + 35

        sig_drawn = False
        if getattr(student, "signature_filename", None):
            sig_p = Config.SIGNATURES_DIR / student.signature_filename
            if sig_p.exists():
                try:
                    s_sig = Image.open(sig_p).convert("RGBA")
                    s_sig.thumbnail((sig_w, 34), Image.Resampling.LANCZOS)
                    centered_sig_x = sig_paste_x + max(0, (sig_w - s_sig.width) // 2)
                    centered_sig_y = sig_baseline_y - s_sig.height - 2
                    img.paste(s_sig, (centered_sig_x, centered_sig_y), s_sig)
                    sig_drawn = True
                except Exception:
                    sig_drawn = False

        # Cardholder signature baseline and label
        draw.line([sig_paste_x, sig_baseline_y, sig_paste_x + sig_w, sig_baseline_y], fill=(148, 163, 184), width=1)
        sig_lbl_font = get_font(11, bold=False)
        draw.text((sig_paste_x + 20, sig_baseline_y + 4), "Cardholder Signature", fill=(100, 116, 139), font=sig_lbl_font)

        # Footer bar text
        foot_font = get_font(17, bold=True)
        draw.text((40, h - footer_height + 18), f"OFFICIAL {school.name.upper()} IDENTIFICATION CREDENTIAL", fill=(255, 255, 255), font=foot_font)
        draw.text((w - 220, h - footer_height + 18), "SERIAL: " + (card_record.card_number if card_record else student.admission_number), fill=(254, 240, 138), font=foot_font)

        return img

    @staticmethod
    def render_back(school, student, card_record, verify_base_url="http://localhost:5000"):
        """Generates Back ID card PIL Image (1011 x 638 px) with Official School Stamp, Principal Signature, and QR code."""
        w, h = LANDSCAPE_W, LANDSCAPE_H
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        pri_rgb = hex_to_rgb(school.primary_color)
        sec_rgb = hex_to_rgb(school.secondary_color)
        text_rgb = hex_to_rgb(school.text_color or "#0F172A")

        # Subtle high-security guilloche watermark background
        if getattr(school, "enable_watermark", True):
            draw_guilloche_watermark(draw, w, h, pri_rgb)

        # Top Header Bar
        top_h = int(h * 0.12)
        draw.rectangle([0, 0, w, top_h], fill=pri_rgb)
        draw.rectangle([0, top_h, w, top_h + 8], fill=sec_rgb)
        
        top_font = get_font(21, bold=True)
        draw.text((35, 18), "CARD TERMS, OFFICIAL STAMP & VERIFICATION", fill=(255, 255, 255), font=top_font)

        # Left Column content area
        left_w = int(w * 0.60)
        sec_title_font = get_font(17, bold=True)
        body_font = get_font(15, bold=False)
        body_bold_font = get_font(15, bold=True)

        draw.text((35, top_h + 20), "TERMS AND CONDITIONS:", fill=pri_rgb, font=sec_title_font)

        disclaimer = school.disclaimer_text or (
            "1. This card remains the property of the school.\n"
            "2. If found, please return to the school administration or nearest police station."
        )

        # ── Disclaimer Block: bold, centred, each line on its own row ────────────
        # Only display the first 2 primary terms prominently on the card back
        raw_lines = [ln.strip() for ln in disclaimer.split("\n") if ln.strip()]
        display_lines = raw_lines[:2]   # Limit to 2 lines for clean block layout

        block_font = get_font(16, bold=True)
        block_line_h = 28                # Height per line
        block_pad_v = 10                 # Top/bottom padding inside the shaded block
        block_x1 = 35
        block_x2 = left_w + 10
        block_y1 = top_h + 46
        block_h = block_pad_v * 2 + block_line_h * len(display_lines)
        block_y2 = block_y1 + block_h

        # Shaded background for the disclaimer block
        draw.rounded_rectangle([block_x1, block_y1, block_x2, block_y2], radius=6,
                                fill=(241, 245, 249), outline=(203, 213, 225), width=1)

        for idx, line in enumerate(display_lines):
            ly = block_y1 + block_pad_v + idx * block_line_h
            # Centre-align each line within the block
            try:
                bbox = block_font.getbbox(line) if hasattr(block_font, "getbbox") else (0, 0, len(line) * 9, 18)
                line_w = bbox[2] - bbox[0]
            except Exception:
                line_w = len(line) * 9
            center_x = block_x1 + (block_x2 - block_x1 - line_w) // 2
            draw.text((max(block_x1 + 6, center_x), ly), line[:80], fill=(15, 23, 42), font=block_font)

        y_cursor = block_y2 + 12

        # Hotline & email separator
        draw.line([35, y_cursor, left_w + 10, y_cursor], fill=(226, 232, 240), width=2)
        y_cursor += 8

        em_font = get_font(15, bold=False)
        em_school_phone = school.emergency_contact_phone or school.phone
        draw.text((35, y_cursor), f"Hotline: {em_school_phone}  •  Email: {school.email or 'admin@school.ac.ke'}", fill=(30, 41, 59), font=em_font)
        y_cursor += 22

        if student.blood_group or getattr(student, "nemis_upi", None):
            bg_text = f"Blood Group: {student.blood_group}" if student.blood_group else ""
            upi_lbl = getattr(school, "upi_label", "NEMIS / UPI") or "NEMIS / UPI"
            upi_text = f" • {upi_lbl}: {student.nemis_upi}" if getattr(student, "nemis_upi", None) else ""
            draw.text((35, y_cursor), f"{bg_text}{upi_text}".strip(" •"), fill=(185, 28, 28), font=get_font(15, bold=True))
            y_cursor += 24

        # ── Authority Verification Block: Official Stamp + Principal's Signature ────
        # Pin the block to a fixed margin ABOVE the bottom footer bar so it is always
        # professionally placed regardless of how much content is above it.
        bottom_h = int(h * 0.12)
        footer_top = h - bottom_h        # y-coordinate where the bottom bar starts
        sig_margin_above_footer = 20     # professional gap between last text and footer

        # Total height needed: stamp ~160, sig area ~90 → use 170 as auth block height
        auth_box_h = 170
        auth_box_y2 = footer_top - sig_margin_above_footer
        auth_box_y = auth_box_y2 - auth_box_h

        draw.rounded_rectangle([35, auth_box_y, left_w + 10, auth_box_y2], radius=8,
                                fill=(248, 250, 252), outline=(226, 232, 240), width=1)

        # ── Official Stamp — left zone, vertically centred in auth block ────────
        try:
            stamp_img = get_official_rubber_stamp(school, size=(155, 155), angle=-8)
            stamp_x = 42
            stamp_y = auth_box_y + max(0, (auth_box_h - stamp_img.height) // 2)
            img.paste(stamp_img, (stamp_x, stamp_y), stamp_img)
        except Exception:
            # Fallback: draw a simple ink-circle so there's always a stamp placeholder
            fc_x = 42 + 77
            fc_y = auth_box_y + auth_box_h // 2
            fc_r = 72
            draw.ellipse([fc_x - fc_r, fc_y - fc_r, fc_x + fc_r, fc_y + fc_r],
                         outline=pri_rgb, width=3)
            draw.ellipse([fc_x - fc_r + 8, fc_y - fc_r + 8,
                          fc_x + fc_r - 8, fc_y + fc_r - 8], outline=pri_rgb, width=1)
            fb_font = get_font(11, bold=True)
            try:
                draw.text((fc_x - 30, fc_y - 8), "OFFICIAL SEAL", fill=pri_rgb, font=fb_font)
            except Exception:
                pass

        # ── Signature zone — right side of auth block ──────────────────────────
        sig_x = 240
        sig_w  = left_w - sig_x - 10
        sig_h  = 52
        sig_y  = auth_box_y + 18

        sig_drawn = False
        if school.principal_signature_filename:
            for s_folder in [Config.SIGNATURES_DIR, Config.LOGOS_DIR, Config.STAMPS_DIR]:
                sig_path = s_folder / school.principal_signature_filename
                if sig_path.exists():
                    try:
                        sig_img = Image.open(sig_path).convert("RGBA")
                        sig_img.thumbnail((sig_w, sig_h), Image.Resampling.LANCZOS)
                        img.paste(sig_img,
                                  (sig_x + (sig_w - sig_img.width) // 2, sig_y),
                                  sig_img)
                        sig_drawn = True
                        break
                    except Exception:
                        sig_drawn = False

        # When no signature image is uploaded, draw a professional cursive placeholder
        if not sig_drawn:
            import math as _math
            ph_y_mid = sig_y + sig_h // 2
            ph_color = (100, 116, 139, 180)   # slate-grey, semi-transparent
            # Create small RGBA overlay for the wavy placeholder line
            sig_overlay = Image.new("RGBA", (sig_w, sig_h + 10), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(sig_overlay)
            pts = []
            for px in range(0, sig_w, 3):
                py = int((sig_h // 2) + _math.sin(px / 12.0) * 7 +
                         _math.sin(px / 5.0 + 1.2) * 3)
                pts.append((px, py))
            for i in range(len(pts) - 1):
                ov_draw.line([pts[i], pts[i + 1]], fill=ph_color, width=2)
            # Second smaller flourish
            pts2 = []
            for px in range(sig_w // 3, sig_w * 2 // 3, 3):
                py = int((sig_h // 2) + 14 + _math.sin(px / 9.0) * 4)
                pts2.append((px, py))
            for i in range(len(pts2) - 1):
                ov_draw.line([pts2[i], pts2[i + 1]], fill=ph_color, width=1)
            img.paste(sig_overlay, (sig_x, sig_y - 5), sig_overlay)

        # Signature baseline — anchored 70 px above the bottom edge of auth block
        line_y = auth_box_y2 - 70
        draw.line([sig_x, line_y, sig_x + sig_w, line_y], fill=(100, 116, 139), width=2)

        # Principal name & title below the baseline
        title_font  = get_font(13, bold=False)
        pname_font  = get_font(14, bold=True)
        signatory_name  = school.principal_name or "Principal / Authorized Signatory"
        signatory_title = getattr(school, "get_signatory_title",
                                  lambda: "Principal / Head of Institution")()
        try:
            draw.text((sig_x + 5, line_y + 5),  signatory_name,  fill=pri_rgb,        font=pname_font)
            draw.text((sig_x + 5, line_y + 23), signatory_title, fill=(71, 85, 105),   font=title_font)
        except Exception:
            pass

        # "[ Authorized Signatory ]" guide label inside auth block
        try:
            stamp_guide_font = get_font(11, bold=False)
            draw.text((sig_x + 5, line_y + 42), "[ Authorized Signatory ]",
                      fill=(148, 163, 184), font=stamp_guide_font)
        except Exception:
            pass

        # Right Column: High-Contrast, Laser-Sharp Optical QR Code & Security Frame
        qr_token = card_record.qr_token if card_record else "DEMO-TOKEN-2026"
        verify_url = f"{verify_base_url.rstrip('/')}/verify/{qr_token}"

        from services.qr_service import QRService
        qr_box_size = 205
        qr_img = QRService.generate_qr_image(verify_url, size_px=qr_box_size, add_shield=True)

        qr_x = w - qr_box_size - 44
        qr_y = top_h + 40

        frame_pad_x = 16
        frame_pad_y = 12
        frame_top = qr_y - frame_pad_y - 22
        frame_bot = qr_y + qr_box_size + frame_pad_y + 46
        frame_left = qr_x - frame_pad_x
        frame_right = qr_x + qr_box_size + frame_pad_x

        # Double border: outer accent line, inner clean white container
        draw.rounded_rectangle([frame_left - 2, frame_top - 2, frame_right + 2, frame_bot + 2], radius=14, fill=sec_rgb)
        draw.rounded_rectangle([frame_left, frame_top, frame_right, frame_bot], radius=12, fill=(255, 255, 255))
        
        # Security Header Banner on container
        draw.rounded_rectangle([frame_left, frame_top, frame_right, frame_top + 24], radius=8, fill=pri_rgb)
        top_badge_font = get_font(12, bold=True)
        draw.text((frame_left + 20, frame_top + 5), "● DIGITAL ID VERIFICATION ●", fill=(255, 255, 255), font=top_badge_font)

        # Targeting Viewfinder Reticles
        b_len = 16
        b_pad = 6
        b_w = 3
        rx1, ry1 = qr_x - b_pad, qr_y - b_pad
        rx2, ry2 = qr_x + qr_box_size + b_pad, qr_y + qr_box_size + b_pad
        reticle_color = pri_rgb

        draw.line([(rx1, ry1), (rx1 + b_len, ry1)], fill=reticle_color, width=b_w)
        draw.line([(rx1, ry1), (rx1, ry1 + b_len)], fill=reticle_color, width=b_w)
        draw.line([(rx2, ry1), (rx2 - b_len, ry1)], fill=reticle_color, width=b_w)
        draw.line([(rx2, ry1), (rx2, ry1 + b_len)], fill=reticle_color, width=b_w)
        draw.line([(rx1, ry2), (rx1 + b_len, ry2)], fill=reticle_color, width=b_w)
        draw.line([(rx1, ry2), (rx1, ry2 - b_len)], fill=reticle_color, width=b_w)
        draw.line([(rx2, ry2), (rx2 - b_len, ry2)], fill=reticle_color, width=b_w)
        draw.line([(rx2, ry2), (rx2 - b_len, ry2)], fill=reticle_color, width=b_w)

        # Paste crisp, optical QR Code
        img.paste(qr_img, (qr_x, qr_y))

        # Bottom label below QR
        scan_font = get_font(13, bold=True)
        draw.text((qr_x + 28, qr_y + qr_box_size + 8), "SCAN TO AUTHENTICATE", fill=pri_rgb, font=scan_font)
        
        token_upper = qr_token.replace("-", "").upper()
        token_chunks = [token_upper[i:i+4] for i in range(0, min(len(token_upper), 16), 4)]
        formatted_token = "-".join(token_chunks) if token_chunks else qr_token[:16]

        token_font = get_font(11, bold=True)
        draw.text((qr_x + 18, qr_y + qr_box_size + 26), f"CODE: {formatted_token}", fill=(71, 85, 105), font=token_font)

        sub_font = get_font(10, bold=False)
        draw.text((qr_x + 10, qr_y + qr_box_size + 42), "SMARTPHONE CAMERA / 2D SCANNER", fill=(148, 163, 184), font=sub_font)

        # Bottom Bar (bottom_h already computed above when anchoring auth block)
        draw.rectangle([0, h - bottom_h, w, h], fill=pri_rgb)
        draw.rectangle([0, h - bottom_h - 4, w, h - bottom_h], fill=sec_rgb)

        foot_font = get_font(16, bold=True)
        draw.text((35, h - bottom_h + 18), f"{school.name.upper()} • {school.town.upper()}", fill=(255, 255, 255), font=foot_font)
        draw.text((w - 290, h - bottom_h + 18), "OFFICIAL SYSTEM ISSUED & DIGITALLY VERIFIED", fill=(254, 240, 138), font=foot_font)

        return img

    @staticmethod
    def save_card_images(school, student, card_record, verify_base_url="http://localhost:5000"):
        """Renders and saves high-resolution front and back PNG images."""
        front = CardRenderer.render_front(school, student, card_record)
        back = CardRenderer.render_back(school, student, card_record, verify_base_url)

        fn_base = f"{school.id}_{student.admission_number}_{card_record.qr_token[:8]}"
        front_fn = f"{fn_base}_front.png"
        back_fn = f"{fn_base}_back.png"

        front_path = Config.GENERATED_CARDS_DIR / front_fn
        back_path = Config.GENERATED_CARDS_DIR / back_fn

        front.save(front_path, "PNG", dpi=(300, 300))
        back.save(back_path, "PNG", dpi=(300, 300))

        card_record.front_image_filename = front_fn
        card_record.back_image_filename = back_fn

        return front_path, back_path

    @staticmethod
    def generate_single_cr80_pdf(front_img_path, back_img_path, output_pdf_path):
        """Generates exact CR80 physical dimension PDF (85.60mm x 53.98mm) for PVC Card Printers.
           Page 1: Front
           Page 2: Back
        """
        w_pt = CR80_W_MM * mm
        h_pt = CR80_H_MM * mm

        c = canvas.Canvas(str(output_pdf_path), pagesize=(w_pt, h_pt))
        
        # Page 1: Front
        c.drawImage(str(front_img_path), 0, 0, width=w_pt, height=h_pt)
        c.showPage()

        # Page 2: Back
        c.drawImage(str(back_img_path), 0, 0, width=w_pt, height=h_pt)
        c.showPage()

        c.save()
        return output_pdf_path

    @staticmethod
    def generate_a4_sheet_pdf(card_image_pairs, output_pdf_path, layout="8_per_page"):
        """Generates A4 sheet layout (210 x 297 mm) for paper proofing or outsourced printing.
           Pairs fronts and backs accurately for standard duplex or sequential cut.
           Default 8 cards per page (2 columns x 4 rows).
        """
        a4_w, a4_h = A4
        c = canvas.Canvas(str(output_pdf_path), pagesize=A4)

        card_w = CR80_W_MM * mm
        card_h = CR80_H_MM * mm

        cols = 2
        rows = 4 if layout == "8_per_page" else 5
        cards_per_sheet = cols * rows

        # Calculate centering margins
        total_grid_w = cols * card_w + (cols - 1) * (4 * mm)
        total_grid_h = rows * card_h + (rows - 1) * (3 * mm)
        margin_x = (a4_w - total_grid_w) / 2
        margin_y = (a4_h - total_grid_h) / 2
        gap_x = 4 * mm
        gap_y = 3 * mm

        # Chunk pairs into sheets
        for i in range(0, len(card_image_pairs), cards_per_sheet):
            batch = card_image_pairs[i:i + cards_per_sheet]

            # FRONT PAGE
            for idx, (f_path, b_path) in enumerate(batch):
                col = idx % cols
                row = idx // cols
                x = margin_x + col * (card_w + gap_x)
                y = a4_h - margin_y - (row + 1) * card_h - row * gap_y
                
                # Draw card
                c.drawImage(str(f_path), x, y, width=card_w, height=card_h)
                
                # Thin crop marks / guidelines
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.5)
                c.rect(x, y, card_w, card_h, stroke=1, fill=0)

            c.showPage()

            # BACK PAGE (Mirrored horizontally for correct double-sided flip)
            for idx, (f_path, b_path) in enumerate(batch):
                col = idx % cols
                # For duplex on long edge, mirror column: 0 -> 1, 1 -> 0
                mirrored_col = (cols - 1) - col
                row = idx // cols
                x = margin_x + mirrored_col * (card_w + gap_x)
                y = a4_h - margin_y - (row + 1) * card_h - row * gap_y

                c.drawImage(str(b_path), x, y, width=card_w, height=card_h)
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.5)
                c.rect(x, y, card_w, card_h, stroke=1, fill=0)

            c.showPage()

        c.save()
        return output_pdf_path

    @staticmethod
    def generate_card_for_student(school, student, base_url="http://localhost:5000", template_id=None):
        """Creates or updates an active CardRecord, renders 300 DPI images,
        generates the print-ready PDF, registers QR token, and marks student active.
        Returns the card record.
        """
        from extensions import db
        from models import CardRecord, QRVerificationToken
        from services.qr_service import QRService

        # Look for existing active card
        existing_card = CardRecord.query.filter_by(student_id=student.id, status="active").first()
        if not existing_card:
            card_number = f"{school.card_prefix or 'ID-'}{student.admission_number}"
            qr_token = QRService.generate_unique_token()
            exp_year = int(student.academic_year) + (school.validity_years or 4)
            expiry_date = datetime.date(exp_year, 12, 31)

            card = CardRecord(
                school_id=school.id,
                student_id=student.id,
                template_id=template_id or school.default_template_id,
                card_number=card_number,
                qr_token=qr_token,
                issue_date=datetime.date.today(),
                expiry_date=expiry_date,
                status="active",
                print_status="pending",
                print_count=0
            )
            db.session.add(card)
            db.session.flush()

            v_token = QRVerificationToken(
                token=qr_token,
                school_id=school.id,
                student_id=student.id,
                card_record_id=card.id,
                is_valid=True
            )
            db.session.add(v_token)
        else:
            card = existing_card

        f_path, b_path = CardRenderer.save_card_images(school, student, card, base_url)

        pdf_fn = f"card_{school.id}_{student.admission_number}_{card.qr_token[:6]}.pdf"
        pdf_path = Config.PDFS_DIR / pdf_fn
        CardRenderer.generate_single_cr80_pdf(f_path, b_path, pdf_path)

        card.single_pdf_filename = pdf_fn
        student.card_status = "active"
        student.card_number = card.card_number
        student.issue_date = card.issue_date
        student.expiry_date = card.expiry_date

        db.session.commit()
        return card

    @staticmethod
    def renew_card_for_student(school, student, base_url="http://localhost:5000",
                               renewal_notes="", template_id=None):
        """Renews a student's ID card:
        - Marks the existing active card as 'renewed' (not deleted).
        - Creates a fresh CardRecord with a new QR token, new expiry date.
        - Renders and saves new 300 DPI front/back images and CR80 PDF.
        - Increments renewal_count for audit trail.
        Returns the new card record.
        """
        from extensions import db
        from models import CardRecord, QRVerificationToken
        from services.qr_service import QRService

        # Archive previous active card as 'renewed'
        old_card = CardRecord.query.filter_by(student_id=student.id, status="active").first()
        old_renewal_count = 0
        if old_card:
            old_renewal_count = (old_card.renewal_count or 0) + 1
            old_card.status = "renewed"
            db.session.flush()

        # Create fresh card record
        card_number = f"{school.card_prefix or 'ID-'}{student.admission_number}"
        qr_token = QRService.generate_unique_token()
        today = datetime.date.today()
        exp_year = today.year + (school.validity_years or 4)
        expiry_date = datetime.date(exp_year, 12, 31)

        new_card = CardRecord(
            school_id=school.id,
            student_id=student.id,
            template_id=template_id or school.default_template_id,
            card_number=card_number,
            qr_token=qr_token,
            issue_date=today,
            expiry_date=expiry_date,
            status="active",
            print_status="pending",
            print_count=0,
            renewal_count=old_renewal_count,
            last_renewed_at=datetime.datetime.utcnow(),
            renewal_notes=renewal_notes or f"Renewed {today.strftime('%d %b %Y')}"
        )
        db.session.add(new_card)
        db.session.flush()

        # Register new QR verification token
        v_token = QRVerificationToken(
            token=qr_token,
            school_id=school.id,
            student_id=student.id,
            card_record_id=new_card.id,
            is_valid=True
        )
        db.session.add(v_token)

        # Render new card images
        f_path, b_path = CardRenderer.save_card_images(school, student, new_card, base_url)

        pdf_fn = f"card_{school.id}_{student.admission_number}_{new_card.qr_token[:6]}.pdf"
        pdf_path = Config.PDFS_DIR / pdf_fn
        CardRenderer.generate_single_cr80_pdf(f_path, b_path, pdf_path)

        new_card.single_pdf_filename = pdf_fn
        student.card_status = "active"
        student.card_number = new_card.card_number
        student.issue_date = new_card.issue_date
        student.expiry_date = new_card.expiry_date

        db.session.commit()
        return new_card
