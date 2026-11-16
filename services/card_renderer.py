import os
import io
import re
import math
import datetime
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter  # type: ignore
try:
    import numpy as np  # type: ignore
except Exception:
    np = None
try:
    import barcode  # type: ignore
    from barcode.writer import ImageWriter  # type: ignore
except Exception:
    barcode = None
    ImageWriter = None
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from config import Config

# Standard CR80 Dimensions in mm and 300 DPI pixels
CR80_W_MM = 85.60
CR80_H_MM = 53.98
DPI = 300

# High-Performance In-Memory Asset Caches (eliminates redundant image processing in bulk generation)
_CLEANED_LOGOS_CACHE = {}
_CLEANED_STAMPS_CACHE = {}
_CLEANED_SIGS_CACHE = {}

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

def fit_font_size(draw, text, max_width, initial_size, min_size=11, bold=False):
    """Dynamically steps down font size until text fits comfortably within max_width."""
    if not text:
        return get_font(initial_size, bold=bold), initial_size
    for sz in range(initial_size, min_size - 1, -1):
        f = get_font(sz, bold=bold)
        try:
            length = draw.textlength(text, font=f)
        except Exception:
            length = len(text) * (sz * 0.55)
        if length <= max_width:
            return f, sz
    return get_font(min_size, bold=bold), min_size

def generate_barcode_img(text, width=224, height=58):
    """Generates an optical, high-contrast Code-128 barcode image for 1D laser scanners."""
    if not text or not barcode or not ImageWriter:
        return None
    try:
        code128 = barcode.get_barcode_class("code128")
        rv = io.BytesIO()
        writer = ImageWriter()
        writer.set_options({
            "module_width": 0.25,
            "module_height": 10.0,
            "quiet_zone": 2.0,
            "write_text": False
        })
        b = code128(str(text), writer=writer)
        b.write(rv)
        rv.seek(0)
        img = Image.open(rv).convert("RGB")
        return img.resize((width, height), Image.Resampling.NEAREST)
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
    micro_font = get_font(11, bold=True)
    if micro_font:
        micro_str = "★ OFFICIAL SECURE CREDENTIAL ★ REPUBLIC OF KENYA ★ CR80 PVC SMART IDENTITY CORE ★ DIGITAL VERIFICATION EMBEDDED ★ "
        micro_color = (
            min(255, int(pri_rgb[0] * 0.18 + 200)),
            min(255, int(pri_rgb[1] * 0.18 + 200)),
            min(255, int(pri_rgb[2] * 0.18 + 205))
        )
        try:
            draw.text((35, int(height * 0.26) + 18), micro_str[:110], fill=micro_color, font=micro_font)
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

def clean_ink_signature(im, ink_color=(20, 50, 135)):
    """Isolates pen ink from paper, transparent canvas, or dark mode backgrounds, producing a crisp,
    transparent, anti-aliased signature rendered in authentic deep institutional blue ink.
    Completely eliminates rectangular dark boxes, canvas transparency artifacts, paper discoloration,
    and dark backgrounds while preserving original pen stroke fidelity, pressure, and curves."""
    if im is None:
        return None
    try:
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        if np is not None:
            arr = np.array(im, dtype=np.float32)
            r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

            # Sample perimeter/border pixels to determine true background color
            borders = np.concatenate([
                arr[0, :, :],      # top row
                arr[-1, :, :],     # bottom row
                arr[:, 0, :],      # left col
                arr[:, -1, :]      # right col
            ])

            border_alpha = borders[:, 3]
            has_alpha = np.any(border_alpha < 240)

            if has_alpha:
                transparent_border_ratio = float(np.mean(border_alpha < 30))
                if transparent_border_ratio > 0.6:
                    # Digital canvas with transparent background
                    ink_mask = a > 20
                    out_a = np.where(ink_mask, np.clip(a * 1.05, 0.0, 255.0), 0.0)

                    target_r, target_g, target_b = ink_color
                    new_r = np.full_like(r, target_r)
                    new_g = np.full_like(g, target_g)
                    new_b = np.full_like(b, target_b)

                    out_arr = np.dstack([new_r, new_g, new_b, out_a]).astype(np.uint8)
                    out = Image.fromarray(out_arr, "RGBA")
                    bbox = out.getbbox()
                    return out.crop(bbox) if bbox else out

            # For opaque images or images where borders have solid background:
            bg_r = float(np.median(borders[:, 0]))
            bg_g = float(np.median(borders[:, 1]))
            bg_b = float(np.median(borders[:, 2]))
            bg_lum = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b

            # Distance in RGB space from the background color
            dist = np.sqrt((r - bg_r)**2 + (g - bg_g)**2 + (b - bg_b)**2)

            if bg_lum >= 120:
                # Light paper (white or off-white)
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                lum_diff = np.maximum(0.0, bg_lum - 8 - lum)
                chroma_diff = dist
                ink_strength = np.maximum(lum_diff * 1.8, chroma_diff * 1.4)
                out_a = np.clip((ink_strength - 18.0) / 45.0 * 255.0, 0.0, 255.0)
            else:
                # Dark background (dark mode canvas, black screen, dark paper)
                # Any pixel distinct from dark background is stroke ink
                out_a = np.clip((dist - 14.0) / 32.0 * 255.0, 0.0, 255.0)

            # Respect existing alpha channel if any
            out_a = np.minimum(out_a, a)

            # Map the ink stroke to deep institutional blue ink (20, 50, 135)
            target_r, target_g, target_b = ink_color
            new_r = np.full_like(r, target_r)
            new_g = np.full_like(g, target_g)
            new_b = np.full_like(b, target_b)

            out_arr = np.dstack([new_r, new_g, new_b, out_a]).astype(np.uint8)
            out = Image.fromarray(out_arr, "RGBA")
            bbox = out.getbbox()
            return out.crop(bbox) if bbox else out
        else:
            gray = im.convert("L")
            alpha = gray.point(lambda p: 255 if p < 140 else (int((215 - p) * 3.4) if p < 215 else 0))
            im.putalpha(alpha)
            bbox = im.getbbox()
            return im.crop(bbox) if bbox else im
    except Exception:
        return im


def format_dob(dob_str):
    """Formats date of birth into DD/MM/YYYY or passes through string."""
    if not dob_str:
        return ""
    import re
    s = str(dob_str).strip()
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m:
        year, month, day = m.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return s


def clean_rubber_stamp(im, target_size=(155, 145), angle=-4):
    """Isolates rubber stamp ink from paper backgrounds, removing rectangular photo borders
    and producing an authentic official institution stamp with clean transparency."""
    if im is None:
        return None
    try:
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        if np is not None:
            arr = np.array(im, dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            color_diff = np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])

            borders = np.concatenate([lum[0, :], lum[-1, :], lum[:, 0], lum[:, -1]])
            bg_lum = max(200.0, float(np.percentile(borders, 85)))

            alpha_color = np.clip((color_diff - 8) * 14.0, 0.0, 235.0)
            alpha_dark = np.clip((bg_lum - 20 - lum) / max(20.0, bg_lum - 20 - 100) * 230.0, 0.0, 230.0)
            alpha = np.maximum(alpha_color, alpha_dark)
            paper_mask = (lum > (bg_lum - 16)) & (color_diff < 12)
            alpha[paper_mask] = 0.0

            # Enhance stamp ink tone
            is_blue = (b > r + 6) & (b > g + 6)
            new_r = np.where(is_blue, np.clip(r * 0.65, 10, 85), r)
            new_g = np.where(is_blue, np.clip(g * 0.65, 20, 95), g)
            new_b = np.where(is_blue, np.clip(b * 1.05 + 10, 130, 235), b)

            out = Image.fromarray(np.dstack([new_r, new_g, new_b, alpha]).astype(np.uint8), "RGBA")
            bbox = out.getbbox()
            if bbox:
                out = out.crop(bbox)
            out.thumbnail(target_size, Image.Resampling.LANCZOS)
            if angle:
                out = out.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
            return out
        else:
            gray = im.convert("L")
            alpha = gray.point(lambda p: 230 if p < 170 else (int((220 - p) * 4.6) if p < 220 else 0))
            im.putalpha(alpha)
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
            im.thumbnail(target_size, Image.Resampling.LANCZOS)
            if angle:
                im = im.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
            return im
    except Exception:
        return im


_STAMP_CLEAN_CACHE = {}
_LOGO_CLEAN_CACHE = {}


def get_official_rubber_stamp(school, size=(155, 145), angle=-4):
    """Generates or loads official institution rubber stamp / seal as a transparent RGBA image with in-memory caching."""
    cache_key = (school.id, getattr(school, "stamp_filename", None), size, angle)
    if cache_key in _STAMP_CLEAN_CACHE:
        return _STAMP_CLEAN_CACHE[cache_key].copy()

    # Check if custom stamp image uploaded
    if getattr(school, "stamp_filename", None):
        for folder in [Config.STAMPS_DIR, Config.SIGNATURES_DIR, Config.LOGOS_DIR]:
            p = folder / school.stamp_filename
            if p.exists():
                try:
                    stamp_raw = Image.open(p)
                    cleaned = clean_rubber_stamp(stamp_raw, target_size=size, angle=angle)
                    if cleaned:
                        _STAMP_CLEAN_CACHE[cache_key] = cleaned
                        return cleaned
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

    result_stamp = stamp.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    _STAMP_CLEAN_CACHE[cache_key] = result_stamp
    return result_stamp


def clean_logo_image(im):
    """Makes outer white/light background of uploaded school logos transparent,
    allowing the card header's primary brand color to show through seamlessly
    without an unsightly rectangular white box around round/custom emblems.
    Preserves all internal white details (e.g., books, stars, banners).
    Includes in-memory caching and intelligent pre-scaling for instant card generation."""
    if im is None:
        return None
    try:
        cache_key = (getattr(im, "filename", None), im.size, im.mode)
        if cache_key[0] and cache_key in _LOGO_CLEAN_CACHE:
            return _LOGO_CLEAN_CACHE[cache_key].copy()

        if im.mode != "RGBA":
            im = im.convert("RGBA")

        # Fast pre-scale if image is high resolution (logo box on card is ~161x100)
        # Prevents costly Python deque iteration over millions of pixels
        if im.width > 300 or im.height > 300:
            im = im.copy()
            im.thumbnail((300, 300), Image.Resampling.LANCZOS)

        if np is None:
            return im

        arr = np.array(im, dtype=np.uint8)
        h, w = arr.shape[:2]

        r = arr[:, :, 0].astype(np.int32)
        g = arr[:, :, 1].astype(np.int32)
        b = arr[:, :, 2].astype(np.int32)
        a = arr[:, :, 3]

        max_c = np.maximum.reduce([r, g, b])
        min_c = np.minimum.reduce([r, g, b])
        is_near_white = (min_c >= 220) & ((max_c - min_c) <= 25)

        visited = np.zeros((h, w), dtype=bool)
        mask_remove = np.zeros((h, w), dtype=bool)
        queue = deque()

        for x in range(w):
            if is_near_white[0, x] and a[0, x] > 0:
                visited[0, x] = True
                queue.append((0, x))
            if is_near_white[h - 1, x] and a[h - 1, x] > 0:
                visited[h - 1, x] = True
                queue.append((h - 1, x))
        for y in range(h):
            if is_near_white[y, 0] and a[y, 0] > 0:
                visited[y, 0] = True
                queue.append((y, 0))
            if is_near_white[y, w - 1] and a[y, w - 1] > 0:
                visited[y, w - 1] = True
                queue.append((y, w - 1))

        while queue:
            cy, cx = queue.popleft()
            mask_remove[cy, cx] = True
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w:
                    if not visited[ny, nx] and is_near_white[ny, nx] and a[ny, nx] > 0:
                        visited[ny, nx] = True
                        queue.append((ny, nx))

        if np.any(mask_remove):
            new_a = a.copy()
            new_a[mask_remove] = 0
            arr[:, :, 3] = new_a
            cleaned = Image.fromarray(arr, "RGBA")
            bbox = cleaned.getbbox()
            if bbox:
                cleaned = cleaned.crop(bbox)
            if cache_key[0]:
                _LOGO_CLEAN_CACHE[cache_key] = cleaned
            return cleaned

        if cache_key[0]:
            _LOGO_CLEAN_CACHE[cache_key] = im
        return im
    except Exception:
        return im


def clean_passport_photo(im, school=None):
    """Safely cleans up passport photo backgrounds while strictly preserving original image quality.
    If auto-whitening is disabled, or if the photo has a textured background (stone/brick/patterns),
    or if whitening would risk encroaching on facial features/highlights, it returns the pristine,
    unmodified original photo to guarantee 100% natural likeness and zero image degradation."""
    if im is None:
        return None
    try:
        im_rgb = im.convert("RGB")
        auto_whiten = getattr(school, "auto_whiten_photo", False) if school else False
        if not auto_whiten:
            return im_rgb  # Preserve 100% original photo quality

        if np is None:
            return im_rgb

        w, h = im_rgb.size
        arr = np.array(im_rgb, dtype=np.float32)

        # Sample top corners for background wall baseline
        sample_h = max(4, int(h * 0.08))
        sample_w = max(4, int(w * 0.12))
        tl = arr[:sample_h, :sample_w].reshape(-1, 3)
        tr = arr[:sample_h, -sample_w:].reshape(-1, 3)
        corners = np.vstack([tl, tr])
        bg_mean = np.median(corners, axis=0)
        bg_std = np.std(corners, axis=0)
        max_std = float(np.max(bg_std)) if len(bg_std) else 10.0
        bg_lum = 0.299 * bg_mean[0] + 0.587 * bg_mean[1] + 0.114 * bg_mean[2]

        # 1. Background must be light and smooth (not textured wall, brick, or dark room)
        if max_std > 18.0 or bg_lum < 135.0:
            return im_rgb  # Preserve pristine original photo

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b

        # 2. Strict protection of human skin and dark hair/features
        is_skin = (r > 55) & (g > 35) & (b > 20) & (r > g) & ((r - b) > 8)
        is_dark = lum < 70

        # 3. Candidate background: must closely match the corner wall sample
        dist = np.sqrt(np.sum((arr - bg_mean) ** 2, axis=2))
        cand = (dist < 26.0) & (~is_skin) & (~is_dark)

        # 4. Strict face protection zone: center oval/box cannot be background
        face_x1, face_x2 = int(w * 0.30), int(w * 0.70)
        face_y1, face_y2 = int(h * 0.20), int(h * 0.55)

        # Flood-fill from top border ONLY
        visited = np.zeros((h, w), dtype=bool)
        bg_mask = np.zeros((h, w), dtype=bool)
        queue = deque()

        for x in range(w):
            if cand[0, x]:
                visited[0, x] = True
                queue.append((0, x))

        while queue:
            cy, cx = queue.popleft()
            bg_mask[cy, cx] = True
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w:
                    if not visited[ny, nx]:
                        visited[ny, nx] = True
                        if cand[ny, nx]:
                            queue.append((ny, nx))

        # 5. Critical check: Did the mask breach into the face zone?
        face_breach = bg_mask[face_y1:face_y2, face_x1:face_x2]
        if np.any(face_breach):
            # Abort immediately if any pixel in the face region was marked
            return im_rgb

        if np.any(bg_mask):
            mask_im = Image.fromarray((bg_mask * 255).astype(np.uint8), "L")
            mask_blurred = mask_im.filter(ImageFilter.GaussianBlur(radius=1.8))
            mask_arr = np.array(mask_blurred, dtype=np.float32) / 255.0
            mask_3d = np.dstack([mask_arr, mask_arr, mask_arr])

            blended = arr * (1.0 - mask_3d) + 255.0 * mask_3d
            res = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), "RGB")
            return res

        return im_rgb
    except Exception:
        return im


class CardRenderer:
    """Production-grade Card Renderer producing high-res 300 DPI PNGs and ReportLab print PDFs."""

    @staticmethod
    def render_front(school, student, card_record=None, template=None):
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
        header_height = int(h * 0.27)
        draw.rectangle([0, 0, w, header_height], fill=pri_rgb)
        
        # Diagonal / Accent stripe under header
        stripe_h = 14
        draw.rectangle([0, header_height, w, header_height + stripe_h], fill=sec_rgb)
        draw.rectangle([0, header_height + stripe_h, w, header_height + stripe_h + 4], fill=acc_rgb)

        # Bottom Footer Bar
        footer_height = int(h * 0.10)
        draw.rectangle([0, h - footer_height, w, h], fill=pri_rgb)
        draw.rectangle([0, h - footer_height - 6, w, h - footer_height], fill=sec_rgb)

        # Student Photo Frame coordinates defined early for geometric alignment
        photo_x = 40
        photo_w = int(w * 0.28) # ~283 px
        photo_center_x = photo_x + photo_w // 2

        # School Logo - Horizontally aligned with the passport photo center for vertical balance
        logo_drawn = False
        logo_box_w, logo_box_h = int(w * 0.16), int(header_height * 0.86)
        logo_x = max(20, photo_center_x - logo_box_w // 2)
        logo_y = int((header_height - logo_box_h) / 2)

        if school.logo_filename:
            logo_path = Config.LOGOS_DIR / school.logo_filename
            if logo_path.exists():
                cache_key = (getattr(school, "id", 0), school.logo_filename, logo_box_w, logo_box_h)
                if cache_key in _CLEANED_LOGOS_CACHE:
                    logo_img = _CLEANED_LOGOS_CACHE[cache_key].copy()
                    actual_logo_x = logo_x + (logo_box_w - logo_img.width) // 2
                    actual_logo_y = logo_y + (logo_box_h - logo_img.height) // 2
                    img.paste(logo_img, (actual_logo_x, actual_logo_y), logo_img)
                    logo_drawn = True
                else:
                    try:
                        raw_logo = Image.open(logo_path)
                        logo_img = clean_logo_image(raw_logo)
                        logo_img.thumbnail((logo_box_w, logo_box_h), Image.Resampling.LANCZOS)
                        _CLEANED_LOGOS_CACHE[cache_key] = logo_img.copy()
                        actual_logo_x = logo_x + (logo_box_w - logo_img.width) // 2
                        actual_logo_y = logo_y + (logo_box_h - logo_img.height) // 2
                        img.paste(logo_img, (actual_logo_x, actual_logo_y), logo_img)
                        logo_drawn = True
                    except Exception:
                        logo_drawn = False

        if not logo_drawn:
            emblem_x = logo_x + (logo_box_w - logo_box_h) // 2
            draw.ellipse([emblem_x, logo_y, emblem_x + logo_box_h, logo_y + logo_box_h], fill=sec_rgb, outline=(255,255,255), width=3)
            emblem_font = get_font(32, bold=True)
            first_letters = "".join([part[0] for part in school.name.split()[:2]]).upper()
            fl_w = int(draw.textlength(first_letters, font=emblem_font))
            draw.text((emblem_x + (logo_box_h - fl_w) // 2, logo_y + 18), first_letters, fill=pri_rgb, font=emblem_font)

        # School Name and details in Header - Centered horizontally for high-prestige executive finish
        text_x = logo_x + logo_box_w + 18
        avail_header_w = w - text_x - 25

        school_name = school.name.upper()
        name_font, _ = fit_font_size(draw, school_name, avail_header_w, initial_size=38, min_size=24, bold=True)
        name_w = int(draw.textlength(school_name, font=name_font))
        name_x = text_x + max(0, (avail_header_w - name_w) // 2)

        curr_hdr_y = logo_y + 2
        draw.text((name_x, curr_hdr_y), school_name, fill=(255, 255, 255), font=name_font)
        curr_hdr_y += 38
        
        motto_text = f'"{school.motto}"' if school.motto else ""
        if motto_text:
            motto_font, _ = fit_font_size(draw, motto_text, avail_header_w, initial_size=18, min_size=13, bold=True)
            motto_w = int(draw.textlength(motto_text, font=motto_font))
            motto_x = text_x + max(0, (avail_header_w - motto_w) // 2)
            draw.text((motto_x, curr_hdr_y), motto_text, fill=(254, 240, 138), font=motto_font)
            curr_hdr_y += 22

        # Dynamic Header Address & Contacts with Minimal Spacing
        show_contacts = getattr(school, "show_header_contacts", True)
        if show_contacts:
            if hasattr(school, "get_header_contact_lines"):
                hdr_lines = school.get_header_contact_lines()
            else:
                hdr_lines = []
                addr_parts = [p for p in [school.po_box, f"{school.town}, {school.county}" if school.town and school.county else (school.town or school.county)] if p]
                if addr_parts:
                    hdr_lines.append(" • ".join(addr_parts))
                if getattr(school, "website", None) and school.website.strip():
                    hdr_lines.append(f"Website: {re.sub(r'^https?://', '', school.website.strip()).rstrip('/')}")
                if getattr(school, "email", None) and school.email.strip():
                    hdr_lines.append(f"Email: {school.email.strip()}")
                if getattr(school, "phone", None) and school.phone.strip():
                    hdr_lines.append(f"Mobile No: {school.phone.strip()}")

            # Minimal spacing between lines: 18px step if 4+ lines, 20px step if 2-3 lines
            line_step = 18 if len(hdr_lines) >= 4 else 20
            for line_str in hdr_lines:
                c_font, _ = fit_font_size(draw, line_str, avail_header_w, initial_size=16, min_size=11, bold=True)
                c_w = int(draw.textlength(line_str, font=c_font))
                c_x = text_x + max(0, (avail_header_w - c_w) // 2)
                draw.text((c_x, curr_hdr_y), line_str, fill=(255, 255, 255), font=c_font)
                curr_hdr_y += line_step

        # Student Photo Frame coordinates
        photo_y = header_height + stripe_h + 20
        photo_h = int(h * 0.51) # ~325 px

        # Badge: Dynamic Card Title (STUDENT / CORPORATE ID CARD)
        card_title_str = getattr(school, "get_card_title", lambda: "STUDENT IDENTITY CARD")()
        badge_w = max(260, len(card_title_str) * 12 + 36)
        badge_h = 32
        badge_x = w - badge_w - 25
        badge_y = header_height + stripe_h + 10
        draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=6, fill=pri_rgb)
        badge_font, _ = fit_font_size(draw, card_title_str, max_width=badge_w - 20, initial_size=16, min_size=12, bold=True)
        badge_lbl_w = int(draw.textlength(card_title_str, font=badge_font))
        draw.text((badge_x + (badge_w - badge_lbl_w) // 2, badge_y + 6), card_title_str, fill=(255, 255, 255), font=badge_font)

        # Academic / Year Tag
        year_w, year_h = 125, 32
        year_x = badge_x - year_w - 10
        draw.rounded_rectangle([year_x, badge_y, year_x + year_w, badge_y + year_h], radius=6, fill=sec_rgb)
        year_font = get_font(16, bold=True)
        year_label = f"YR {student.academic_year}" if getattr(school, "is_corporate", lambda: False)() else f"AY {student.academic_year}"
        year_lbl_w = int(draw.textlength(year_label, font=year_font))
        draw.text((year_x + (year_w - year_lbl_w) // 2, badge_y + 6), year_label, fill=(15, 23, 42), font=year_font)

        # Renewal Stamp Badge (if card has been renewed) - Aligned cleanly in badge bar with zero overlap
        renewal_cnt = (getattr(card_record, "renewal_count", 0) or 0) if card_record else 0
        if renewal_cnt > 0:
            ren_w = 135
            photo_right_bound = photo_x + photo_w + 14
            ren_x = max(photo_right_bound, year_x - ren_w - 12)
            draw.rounded_rectangle([ren_x, badge_y, ren_x + ren_w, badge_y + badge_h], radius=6, fill=(16, 185, 129))
            ren_font = get_font(14, bold=True)
            ren_str = f"RENEWED R{renewal_cnt}"
            ren_lbl_w = int(draw.textlength(ren_str, font=ren_font))
            draw.text((ren_x + (ren_w - ren_lbl_w) // 2, badge_y + 8), ren_str, fill=(255, 255, 255), font=ren_font)

        # Outer luxury double border: metallic gold outer, clean white inner spacer
        draw.rounded_rectangle([photo_x - 3, photo_y - 3, photo_x + photo_w + 3, photo_y + photo_h + 3], radius=8, fill=sec_rgb)
        draw.rounded_rectangle([photo_x - 1, photo_y - 1, photo_x + photo_w + 1, photo_y + photo_h + 1], radius=7, fill=(255, 255, 255))
        draw.rounded_rectangle([photo_x, photo_y, photo_x + photo_w, photo_y + photo_h], radius=6, fill=(240, 244, 248))

        # Paste Photo
        photo_pasted = False
        preview_photo = getattr(student, "preview_photo", None)
        if preview_photo is not None:
            try:
                cleaned_photo = clean_passport_photo(preview_photo, school=school)
                s_photo = ImageOps.fit(cleaned_photo, (photo_w, photo_h), Image.Resampling.LANCZOS)
                img.paste(s_photo, (photo_x, photo_y))
                photo_pasted = True
            except Exception:
                photo_pasted = False
        target_photo_fn = student.photo_cropped_filename or student.photo_filename
        if not photo_pasted and target_photo_fn:
            photo_path = Config.PHOTOS_DIR / target_photo_fn
            if photo_path.exists():
                try:
                    raw_photo = Image.open(photo_path)
                    cleaned_photo = clean_passport_photo(raw_photo, school=school)
                    s_photo = ImageOps.fit(cleaned_photo, (photo_w, photo_h), Image.Resampling.LANCZOS)
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

        # ── Sub-Photo Identification Badge (ADM NO / EMP NO / REG NO) ───────────
        sub_badge_y = photo_y + photo_h + 10
        sub_badge_h = 32
        sub_label = school.get_sub_photo_label() if hasattr(school, "get_sub_photo_label") else "ADM NO"
        sub_text = f"{sub_label}: {student.admission_number}"
        draw.rounded_rectangle([photo_x, sub_badge_y, photo_x + photo_w, sub_badge_y + sub_badge_h], radius=6, fill=pri_rgb)
        sub_font, _ = fit_font_size(draw, sub_text, max_width=photo_w - 12, initial_size=18, min_size=13, bold=True)
        sub_text_w = int(draw.textlength(sub_text, font=sub_font))
        draw.text((photo_x + (photo_w - sub_text_w) // 2, sub_badge_y + 6), sub_text, fill=(255, 255, 255), font=sub_font)

        # Information Block with Dynamic Labels and Perfect Harmonized Column Offsets
        info_x = photo_x + photo_w + 92
        start_y = header_height + stripe_h + 60
        line_spacing = 33

        # Smart Gold Contactless Security Chip beside photo - positioned clearly below the top badges lane
        if getattr(school, "enable_smart_chip", True):
            draw_smart_chip(draw, photo_x + photo_w + 18, start_y + 10, w=56, h=44)

        lbl_font = get_font(20, bold=True)
        val_font = get_font(24, bold=True)

        id_lbl_text = f"{getattr(school, 'get_id_label', lambda: 'ADM NO')()}:"
        class_lbl_text = f"{getattr(school, 'get_class_label', lambda: 'CLASS / GRADE')()}:"

        # Column 2 value start offset (guaranteed 175px label space - never collides)
        col2_x = info_x + 175
        avail_val_w = (w - 35) - col2_x  # available width for values without margin collision

        # 1. Full Name with auto font-scaling for longer names
        draw.text((info_x, start_y), "NAME:", fill=(100, 116, 139), font=lbl_font)
        clean_full_name = student.full_name.upper()
        name_font_to_use, _ = fit_font_size(draw, clean_full_name, avail_val_w, initial_size=30, min_size=18, bold=True)
        draw.text((col2_x, start_y - 3), clean_full_name, fill=pri_rgb, font=name_font_to_use)

        # 2. Date of Birth (fully aligned above ADM NO)
        curr_y = start_y + line_spacing
        draw.text((info_x, curr_y), "D.O.B:", fill=(100, 116, 139), font=lbl_font)
        dob_raw = getattr(student, "dob", "") or ""
        dob_display = format_dob(dob_raw) or "-"
        draw.text((col2_x, curr_y), dob_display, fill=text_rgb, font=val_font)

        # 3. Gender (fully aligned with all components above ADM NO)
        curr_y += line_spacing
        draw.text((info_x, curr_y), "GENDER:", fill=(100, 116, 139), font=lbl_font)
        gender_display = (getattr(student, "gender", "") or "-").strip().upper()
        draw.text((col2_x, curr_y), gender_display, fill=text_rgb, font=val_font)

        # 4. ID / Admission Number
        curr_y += line_spacing
        draw.text((info_x, curr_y), id_lbl_text, fill=(100, 116, 139), font=lbl_font)
        draw.text((col2_x, curr_y), student.admission_number, fill=text_rgb, font=val_font)

        # Class / Department & Stream (properly spaced in column 2, auto-scaled to prevent overflow)
        curr_y += line_spacing
        draw.text((info_x, curr_y), class_lbl_text, fill=(100, 116, 139), font=lbl_font)
        cls_stream_str = f"{student.class_name} {student.stream_name or ''}".strip()
        cls_font_to_use, _ = fit_font_size(draw, cls_stream_str, avail_val_w, initial_size=24, min_size=16, bold=True)
        draw.text((col2_x, curr_y), cls_stream_str, fill=text_rgb, font=cls_font_to_use)

        # Card Number
        curr_y += line_spacing
        draw.text((info_x, curr_y), "CARD NO:", fill=(100, 116, 139), font=lbl_font)
        card_no = card_record.card_number if card_record else f"{school.card_prefix or 'ID-'}{student.admission_number}"
        card_no_font, _ = fit_font_size(draw, card_no, avail_val_w, initial_size=24, min_size=16, bold=True)
        draw.text((col2_x, curr_y), card_no, fill=text_rgb, font=card_no_font)

        # Valid Until / Expiry
        curr_y += line_spacing
        draw.text((info_x, curr_y), "EXPIRES:", fill=(100, 116, 139), font=lbl_font)
        exp_year = card_record.expiry_date.year if card_record and card_record.expiry_date else int(student.academic_year) + (school.validity_years or 4)
        exp_date_str = f"DEC {exp_year}"
        draw.text((col2_x, curr_y), exp_date_str, fill=(220, 38, 38), font=val_font)

        # ── Cardholder Signature Zone ──────────────────────────────────────────
        # Lifted safely above the bottom footer margin (raised by 20px from initial -50)
        # Guarantees a comfortable ~18px breathing space above the footer accent line
        sig_w = 160
        sig_paste_x = w - sig_w - 28
        sig_paste_y = h - footer_height - 72
        sig_baseline_y = sig_paste_y + 34

        preview_signature = getattr(student, "preview_signature", None)
        if preview_signature is not None:
            try:
                s_sig = clean_ink_signature(preview_signature, ink_color=(20, 50, 135))
                if s_sig:
                    s_sig.thumbnail((sig_w - 8, 36), Image.Resampling.LANCZOS)
                    centered_sig_x = sig_paste_x + max(0, (sig_w - s_sig.width) // 2)
                    centered_sig_y = sig_baseline_y - s_sig.height - 2
                    img.paste(s_sig, (centered_sig_x, centered_sig_y), s_sig)
            except Exception:
                pass
        elif getattr(student, "signature_filename", None):
            sig_p = Config.SIGNATURES_DIR / student.signature_filename
            if sig_p.exists():
                try:
                    raw_s = Image.open(sig_p)
                    s_sig = clean_ink_signature(raw_s, ink_color=(20, 50, 135))
                    if s_sig:
                        s_sig.thumbnail((sig_w - 8, 36), Image.Resampling.LANCZOS)
                        centered_sig_x = sig_paste_x + max(0, (sig_w - s_sig.width) // 2)
                        centered_sig_y = sig_baseline_y - s_sig.height - 2
                        img.paste(s_sig, (centered_sig_x, centered_sig_y), s_sig)
                except Exception:
                    pass

        # Cardholder signature baseline and label
        draw.line([sig_paste_x, sig_baseline_y, sig_paste_x + sig_w, sig_baseline_y], fill=(148, 163, 184), width=1)
        sig_lbl_font = get_font(13, bold=True)
        sig_lbl_w = int(draw.textlength("Cardholder Signature", font=sig_lbl_font))
        draw.text((sig_paste_x + (sig_w - sig_lbl_w) // 2, sig_baseline_y + 4), "Cardholder Signature", fill=(100, 116, 139), font=sig_lbl_font)

        # Footer bar text with collision protection
        serial_str = "SERIAL: " + (card_record.card_number if card_record else student.admission_number)
        serial_font = get_font(20, bold=True)
        serial_w = 260
        foot_str = f"OFFICIAL {school.name.upper()} IDENTIFICATION CREDENTIAL"
        foot_font, _ = fit_font_size(draw, foot_str, max_width=w - serial_w - 70, initial_size=20, min_size=14, bold=True)
        draw.text((40, h - footer_height + 18), foot_str, fill=(255, 255, 255), font=foot_font)
        draw.text((w - serial_w, h - footer_height + 18), serial_str, fill=(254, 240, 138), font=serial_font)

        return img

    @staticmethod
    def render_back(school, student, card_record=None, verify_base_url="http://localhost:5000"):
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

        # Top Header Bar - Centered on ID card for high-level institutional presentation
        top_h = int(h * 0.12)
        draw.rectangle([0, 0, w, top_h], fill=pri_rgb)
        draw.rectangle([0, top_h, w, top_h + 8], fill=sec_rgb)
        
        top_hdr_str = "CARD TERMS, OFFICIAL STAMP & VERIFICATION"
        top_font, _ = fit_font_size(draw, top_hdr_str, max_width=w - 60, initial_size=25, min_size=18, bold=True)
        top_hdr_w = int(draw.textlength(top_hdr_str, font=top_font))
        draw.text(((w - top_hdr_w) // 2, (top_h - 26) // 2), top_hdr_str, fill=(255, 255, 255), font=top_font)

        # Left Column content area
        # Left Column content area - widened to 70% width (~707px) for world-class spacious card layout
        left_w = int(w * 0.70)

        # ── Authority Verification Block geometry (computed first to anchor vertical rhythm) ──
        bottom_h = int(h * 0.12)
        footer_top = h - bottom_h
        sig_margin_above_footer = 28
        auth_box_h = 168
        auth_box_y2 = footer_top - sig_margin_above_footer  # y = 534
        auth_box_y = auth_box_y2 - auth_box_h               # y = 366

        # ── Harmonized Terms & Conditions Institutional Block ───────────────────
        # Matches the Auth Block geometry directly below it:
        # Same x-boundaries ([35, left_w + 8]), same corner radius (8px),
        # same subtle container styling with integrated header banner.
        t_box_x1 = 35
        t_box_x2 = left_w + 8
        t_box_y1 = top_h + 16
        t_box_y2 = auth_box_y - 14

        # Container card with rounded corners and subtle border
        draw.rounded_rectangle([t_box_x1, t_box_y1, t_box_x2, t_box_y2], radius=8,
                               fill=(248, 250, 252), outline=(226, 232, 240), width=1)

        # Header banner inside the block - Centered
        banner_h = 32
        draw.rounded_rectangle([t_box_x1, t_box_y1, t_box_x2, t_box_y1 + banner_h], radius=8, fill=pri_rgb)
        draw.rectangle([t_box_x1, t_box_y1 + banner_h - 6, t_box_x2, t_box_y1 + banner_h], fill=pri_rgb)

        terms_hdr_font = get_font(14, bold=True)
        terms_hdr_str = "● TERMS & CONDITIONS OF ISSUANCE ●"
        t_hdr_w = int(draw.textlength(terms_hdr_str, font=terms_hdr_font))
        draw.text((t_box_x1 + (t_box_x2 - t_box_x1 - t_hdr_w) // 2, t_box_y1 + 7), terms_hdr_str, fill=(255, 255, 255), font=terms_hdr_font)

        # Disclaimers / Terms text - Left-aligned block starting at the same uniform X position
        if hasattr(school, "get_disclaimer_lines"):
            raw_lines = school.get_disclaimer_lines()
        else:
            disclaimer = school.disclaimer_text or (
                "1. This card remains the property of the institution.\n"
                "2. If found, please return to the administration or nearest police station.\n"
                "3. The card must be carried at all times within premises.\n"
                "4. The card must be carried anytime when representing the institution."
            )
            raw_lines = [ln.strip() for ln in disclaimer.replace("\r", "").split("\n") if ln.strip()]

        start_x = t_box_x1 + 18
        term_y = t_box_y1 + banner_h + 8
        line_step = 19
        # Display up to 4 terms lines cleanly
        for line in raw_lines[:4]:
            term_line_font, _ = fit_font_size(draw, line, max_width=t_box_x2 - start_x - 16, initial_size=12, min_size=10, bold=True)
            draw.text((start_x, term_y), line, fill=(15, 23, 42), font=term_line_font)
            term_y += line_step

        # Hairline divider inside block
        term_div_y = max(term_y + 4, t_box_y1 + banner_h + 84)
        draw.line([t_box_x1 + 16, term_div_y, t_box_x2 - 16, term_div_y], fill=(226, 232, 240), width=1)

        # Dedicated school contact block; parent/guardian phone numbers stay private.
        em_school_phone = school.emergency_contact_phone or school.phone or "N/A"
        contact_y = term_div_y + 8
        contact_width = t_box_x2 - start_x - 16
        contact_heading_font = get_font(13, bold=True)
        draw.text((start_x, contact_y), "SCHOOL CONTACT", fill=pri_rgb, font=contact_heading_font)
        contact_lines = [
            f"Hotline: {em_school_phone}",
            f"Email: {school.email or 'Not provided'}",
            f"Website: {school.website or 'Not provided'}"
        ]
        for line_index, contact_line in enumerate(contact_lines):
            line_font, _ = fit_font_size(draw, contact_line, contact_width, initial_size=13, min_size=10, bold=False)
            draw.text((start_x, contact_y + 18 + line_index * 17), contact_line, fill=(51, 65, 85), font=line_font)
        meta_y = contact_y + 72

        # NEMIS / UPI row
        upi_lbl = getattr(school, "upi_label", "NEMIS / UPI") or "NEMIS / UPI"
        if getattr(student, "nemis_upi", None):
            draw.text((start_x, meta_y), f"{upi_lbl}: {student.nemis_upi}", fill=(185, 28, 28), font=get_font(14, bold=True))
        else:
            std_rec_font = get_font(12, bold=False)
            draw.text((start_x, meta_y), "Official institutional record • Verification required upon presentation.", fill=(100, 116, 139), font=std_rec_font)

        # ── Authority Verification Block: Official Stamp + Principal's Signature ────
        auth_box_h = auth_box_y2 - auth_box_y
        draw.rounded_rectangle([35, auth_box_y, left_w + 8, auth_box_y2], radius=8,
                                fill=(255, 255, 255), outline=(226, 232, 240), width=1)

        # ── Official Stamp — left zone, vertically and horizontally centred in stamp area ────
        try:
            stamp_key = (getattr(school, "id", 0), getattr(school, "stamp_filename", None), getattr(school, "primary_color", None))
            if stamp_key in _CLEANED_STAMPS_CACHE:
                stamp_img = _CLEANED_STAMPS_CACHE[stamp_key].copy()
            else:
                stamp_img = get_official_rubber_stamp(school, size=(150, 140), angle=-4)
                if stamp_img:
                    _CLEANED_STAMPS_CACHE[stamp_key] = stamp_img.copy()
            if stamp_img:
                stamp_x = 42 + max(0, (165 - stamp_img.width) // 2)
                stamp_y = auth_box_y + max(0, (auth_box_h - stamp_img.height) // 2)
                img.paste(stamp_img, (stamp_x, stamp_y), stamp_img)
            else:
                raise ValueError("No stamp")
        except Exception:
            # Fallback: draw a simple ink-circle so there's always a stamp placeholder
            fc_x = 42 + 75
            fc_y = auth_box_y + auth_box_h // 2
            fc_r = 65
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
        sig_x = 210
        sig_w = (left_w + 8) - sig_x - 15  # ~273 px
        sig_h = 60
        line_y = auth_box_y2 - 58

        sig_drawn = False
        sig_cache_key = (getattr(school, "id", 0), getattr(school, "principal_signature_filename", None), sig_w, sig_h)
        if sig_cache_key in _CLEANED_SIGS_CACHE:
            cached_sig = _CLEANED_SIGS_CACHE[sig_cache_key]
            if cached_sig is not None:
                sig_paste_x = sig_x + max(0, (sig_w - cached_sig.width) // 2)
                sig_paste_y = line_y - cached_sig.height - 4
                img.paste(cached_sig, (sig_paste_x, sig_paste_y), cached_sig)
                sig_drawn = True
        elif school.principal_signature_filename:
            for s_folder in [Config.SIGNATURES_DIR, Config.LOGOS_DIR, Config.STAMPS_DIR]:
                sig_path = s_folder / school.principal_signature_filename
                if sig_path.exists():
                    try:
                        raw_sig = Image.open(sig_path)
                        sig_img = clean_ink_signature(raw_sig, ink_color=(20, 50, 135))
                        if sig_img:
                            sig_img.thumbnail((sig_w - 20, sig_h), Image.Resampling.LANCZOS)
                            _CLEANED_SIGS_CACHE[sig_cache_key] = sig_img.copy()
                            sig_paste_x = sig_x + max(0, (sig_w - sig_img.width) // 2)
                            sig_paste_y = line_y - sig_img.height - 4
                            img.paste(sig_img, (sig_paste_x, sig_paste_y), sig_img)
                            sig_drawn = True
                            break
                    except Exception:
                        sig_drawn = False

        # When no signature image is uploaded, draw a professional cursive placeholder in deep blue ink
        if not sig_drawn:
            import math as _math
            ph_color = (20, 50, 135, 195)   # deep institutional blue ink
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
            img.paste(sig_overlay, (sig_x, line_y - sig_h - 2), sig_overlay)

        # Signature baseline — anchored above signatory titles
        draw.line([sig_x, line_y, sig_x + sig_w, line_y], fill=(148, 163, 184), width=1)

        # Principal name & title below the baseline (auto-scaled and centered)
        signatory_name  = school.principal_name or "Principal"
        signatory_title = getattr(school, "get_signatory_title",
                                  lambda: "Principal / Head of Institution")()
        pname_font, _ = fit_font_size(draw, signatory_name, max_width=sig_w - 10, initial_size=16, min_size=12, bold=True)
        title_font, _ = fit_font_size(draw, signatory_title, max_width=sig_w - 10, initial_size=13, min_size=11, bold=False)
        try:
            pname_w = int(draw.textlength(signatory_name, font=pname_font))
            title_w = int(draw.textlength(signatory_title, font=title_font))
            pname_x = sig_x + max(0, (sig_w - pname_w) // 2)
            title_x = sig_x + max(0, (sig_w - title_w) // 2)
            draw.text((pname_x, line_y + 5),  signatory_name,  fill=pri_rgb,        font=pname_font)
            draw.text((title_x, line_y + 26), signatory_title, fill=(71, 85, 105),   font=title_font)
        except Exception:
            pass

        # ── Right Column: Harmonized Digital QR Code & Optical Code-128 Barcode ─────
        rc_x1 = left_w + 18
        rc_x2 = w - 25
        rc_w = rc_x2 - rc_x1  # ~261 px

        # 1. Top Container: Digital ID Verification (QR Code)
        qr_token = card_record.qr_token if card_record else "DEMO-TOKEN-2026"
        verify_url = f"{verify_base_url.rstrip('/')}/verify/{qr_token}"

        from services.qr_service import QRService
        qr_box_size = 145
        qr_img = QRService.generate_qr_image(verify_url, size_px=qr_box_size, add_shield=True)

        qr_frame_y1 = t_box_y1
        qr_frame_y2 = t_box_y2

        # Double border
        draw.rounded_rectangle([rc_x1 - 2, qr_frame_y1 - 2, rc_x2 + 2, qr_frame_y2 + 2], radius=12, fill=sec_rgb)
        draw.rounded_rectangle([rc_x1, qr_frame_y1, rc_x2, qr_frame_y2], radius=10, fill=(255, 255, 255))

        # Security Header Banner - Centered
        banner_qr_h = 26
        draw.rounded_rectangle([rc_x1, qr_frame_y1, rc_x2, qr_frame_y1 + banner_qr_h], radius=8, fill=pri_rgb)
        draw.rectangle([rc_x1, qr_frame_y1 + banner_qr_h - 4, rc_x2, qr_frame_y1 + banner_qr_h], fill=pri_rgb)
        qr_hdr_font = get_font(12, bold=True)
        qr_hdr_str = "● DIGITAL ID VERIFICATION ●"
        qr_hdr_w = int(draw.textlength(qr_hdr_str, font=qr_hdr_font))
        draw.text((rc_x1 + (rc_w - qr_hdr_w) // 2, qr_frame_y1 + 5), qr_hdr_str, fill=(255, 255, 255), font=qr_hdr_font)

        # Center QR code
        qr_x = rc_x1 + (rc_w - qr_box_size) // 2
        qr_y = qr_frame_y1 + banner_qr_h + 8

        # Targeting Viewfinder Reticles
        b_len = 14
        b_pad = 5
        b_w = 2
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

        # Paste QR
        img.paste(qr_img, (qr_x, qr_y))

        # Under QR - Centered cleanly with enhanced font sizes
        scan_font = get_font(13, bold=True)
        scan_str = "SCAN TO AUTHENTICATE"
        scan_w = int(draw.textlength(scan_str, font=scan_font))
        draw.text((rc_x1 + (rc_w - scan_w) // 2, qr_y + qr_box_size + 6), scan_str, fill=pri_rgb, font=scan_font)

        token_upper = qr_token.replace("-", "").upper()
        token_chunks = [token_upper[i:i+4] for i in range(0, min(len(token_upper), 16), 4)]
        formatted_token = "-".join(token_chunks) if token_chunks else qr_token[:16]

        token_font = get_font(11, bold=True)
        code_str = f"CODE: {formatted_token}"
        code_w = int(draw.textlength(code_str, font=token_font))
        draw.text((rc_x1 + (rc_w - code_w) // 2, qr_y + qr_box_size + 24), code_str, fill=(71, 85, 105), font=token_font)

        sub_font = get_font(10, bold=False)
        sub_str = "SMARTPHONE CAMERA / 2D SCANNER"
        sub_w = int(draw.textlength(sub_str, font=sub_font))
        draw.text((rc_x1 + (rc_w - sub_w) // 2, qr_y + qr_box_size + 40), sub_str, fill=(148, 163, 184), font=sub_font)

        # 2. Bottom Container: Optical Code-128 Barcode (Library, Gate & Canteen)
        bc_frame_y1 = auth_box_y
        bc_frame_y2 = auth_box_y2  # perfectly harmonized with bottom of auth block (y = 534)

        draw.rounded_rectangle([rc_x1 - 2, bc_frame_y1 - 2, rc_x2 + 2, bc_frame_y2 + 2], radius=12, fill=sec_rgb)
        draw.rounded_rectangle([rc_x1, bc_frame_y1, rc_x2, bc_frame_y2], radius=10, fill=(255, 255, 255))

        # Barcode Header Banner - Centered
        banner_bc_h = 26
        draw.rounded_rectangle([rc_x1, bc_frame_y1, rc_x2, bc_frame_y1 + banner_bc_h], radius=8, fill=pri_rgb)
        draw.rectangle([rc_x1, bc_frame_y1 + banner_bc_h - 4, rc_x2, bc_frame_y1 + banner_bc_h], fill=pri_rgb)
        bc_hdr_font = get_font(12, bold=True)
        bc_hdr_str = "● LIBRARY & GATE BARCODE ●"
        bc_hdr_w = int(draw.textlength(bc_hdr_str, font=bc_hdr_font))
        draw.text((rc_x1 + (rc_w - bc_hdr_w) // 2, bc_frame_y1 + 5), bc_hdr_str, fill=(255, 255, 255), font=bc_hdr_font)

        # Render and paste Code-128 Barcode
        bc_val = student.admission_number or (card_record.card_number if card_record else "ID-000")
        bc_w = min(226, rc_w - 20)
        bc_h = 56
        bc_img = generate_barcode_img(bc_val, width=bc_w, height=bc_h)
        if bc_img:
            bc_paste_x = rc_x1 + (rc_w - bc_w) // 2
            bc_paste_y = bc_frame_y1 + banner_bc_h + 8
            img.paste(bc_img, (bc_paste_x, bc_paste_y))

        # Under Barcode: Human readable admission number & compatibility (Centered)
        bc_txt_y = bc_frame_y1 + banner_bc_h + 8 + bc_h + 4
        num_font = get_font(15, bold=True)
        num_text = f"* {bc_val} *"
        try:
            num_w = int(draw.textlength(num_text, font=num_font))
            draw.text((rc_x1 + (rc_w - num_w) // 2, bc_txt_y), num_text, fill=text_rgb, font=num_font)
        except Exception:
            draw.text((rc_x1 + 35, bc_txt_y), num_text, fill=text_rgb, font=num_font)

        compat_font = get_font(11, bold=True)
        compat_str = "1D LASER SCANNER COMPATIBLE"
        compat_w = int(draw.textlength(compat_str, font=compat_font))
        draw.text((rc_x1 + (rc_w - compat_w) // 2, bc_txt_y + 19), compat_str, fill=pri_rgb, font=compat_font)

        sys_font = get_font(10, bold=False)
        sys_str = "KOHA / GATE / CANTEEN POS"
        sys_w = int(draw.textlength(sys_str, font=sys_font))
        draw.text((rc_x1 + (rc_w - sys_w) // 2, bc_txt_y + 35), sys_str, fill=(148, 163, 184), font=sys_font)

        # ── Legal & Security Warning Notice: Centered at the bottom of the card in BOLD RED ──
        if getattr(school, "show_security_notice", True):
            notice_text = (getattr(school, "security_notice", None) or "Official institutional credential. Unlawful alteration or possession is prohibited.").strip()
            if notice_text:
                notice_font, _ = fit_font_size(draw, notice_text, max_width=w - 50, initial_size=13, min_size=10, bold=True)
                notice_w = int(draw.textlength(notice_text, font=notice_font))
                notice_x = (w - notice_w) // 2
                notice_y = footer_top - 23
                draw.text((notice_x, notice_y), notice_text, fill=(220, 38, 38), font=notice_font)

        # Bottom Bar
        draw.rectangle([0, h - bottom_h, w, h], fill=pri_rgb)
        draw.rectangle([0, h - bottom_h - 4, w, h - bottom_h], fill=sec_rgb)

        foot_left_str = f"{school.name.upper()} • {school.town.upper()}"
        foot_right_str = "OFFICIAL SYSTEM ISSUED & DIGITALLY VERIFIED"
        foot_right_font, _ = fit_font_size(draw, foot_right_str, max_width=int(w * 0.44), initial_size=18, min_size=12, bold=True)
        try:
            foot_right_width = int(draw.textlength(foot_right_str, font=foot_right_font))
        except Exception:
            foot_right_width = min(int(w * 0.44), len(foot_right_str) * 10)
        foot_right_x = w - 35 - foot_right_width
        foot_left_font, _ = fit_font_size(draw, foot_left_str, max_width=max(100, foot_right_x - 55), initial_size=18, min_size=12, bold=True)
        draw.text((35, h - bottom_h + 18), foot_left_str, fill=(255, 255, 255), font=foot_left_font)
        draw.text((foot_right_x, h - bottom_h + 18), foot_right_str, fill=(254, 240, 138), font=foot_right_font)

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
        """Generates A4 sheet layout (210 x 297 mm) for paper proofing, Teslin, or outsourced printing.
           Pairs fronts and backs accurately for standard duplex or sequential cut.
           Default 8 cards per page (2 columns x 4 rows) or 10 cards per page (2 columns x 5 rows).
           Includes professional corner crop marks (3.5mm ticks) and subtle alignment guides.
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

        def draw_crop_marks(canvas_obj, x, y, w, h):
            """Draws standard 3.5mm corner tick marks extending outside the card boundary."""
            tick = 3.5 * mm
            gap = 0.8 * mm
            canvas_obj.setStrokeColorRGB(0.4, 0.4, 0.4)
            canvas_obj.setLineWidth(0.35)

            # Top-Left corner ticks
            canvas_obj.line(x - tick - gap, y + h, x - gap, y + h)
            canvas_obj.line(x, y + h + gap, x, y + h + gap + tick)

            # Top-Right corner ticks
            canvas_obj.line(x + w + gap, y + h, x + w + gap + tick, y + h)
            canvas_obj.line(x + w, y + h + gap, x + w, y + h + gap + tick)

            # Bottom-Left corner ticks
            canvas_obj.line(x - tick - gap, y, x - gap, y)
            canvas_obj.line(x, y - gap - tick, x, y - gap)

            # Bottom-Right corner ticks
            canvas_obj.line(x + w + gap, y, x + w + gap + tick, y)
            canvas_obj.line(x + w, y - gap - tick, x + w, y - gap)

            # Very subtle boundary guide for positioning
            canvas_obj.setStrokeColorRGB(0.85, 0.85, 0.85)
            canvas_obj.setLineWidth(0.25)
            canvas_obj.rect(x, y, w, h, stroke=1, fill=0)

        total_sheets = max(1, math.ceil(len(card_image_pairs) / cards_per_sheet))

        # Chunk pairs into sheets
        for sheet_idx, i in enumerate(range(0, len(card_image_pairs), cards_per_sheet), start=1):
            batch = card_image_pairs[i:i + cards_per_sheet]

            # FRONT PAGE
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawString(margin_x, a4_h - margin_y + 4 * mm,
                         f"EduID Kenya Print Production Sheet (A4) — CR80 85.60 × 53.98 mm — Side: FRONT — Sheet {sheet_idx} of {total_sheets}")
            c.setFont("Helvetica", 7)
            c.drawRightString(a4_w - margin_x, a4_h - margin_y + 4 * mm,
                              f"Batch Items {i + 1} to {min(i + len(batch), len(card_image_pairs))} of {len(card_image_pairs)}")

            for idx, (f_path, b_path) in enumerate(batch):
                col = idx % cols
                row = idx // cols
                x = margin_x + col * (card_w + gap_x)
                y = a4_h - margin_y - (row + 1) * card_h - row * gap_y
                
                # Draw card
                c.drawImage(str(f_path), x, y, width=card_w, height=card_h)
                draw_crop_marks(c, x, y, card_w, card_h)

            c.showPage()

            # BACK PAGE (Mirrored horizontally for correct double-sided flip)
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawString(margin_x, a4_h - margin_y + 4 * mm,
                         f"EduID Kenya Print Production Sheet (A4) — CR80 85.60 × 53.98 mm — Side: BACK (Duplex Long-Edge Flip) — Sheet {sheet_idx} of {total_sheets}")
            c.setFont("Helvetica", 7)
            c.drawRightString(a4_w - margin_x, a4_h - margin_y + 4 * mm, "Standard Duplex / Rotary Trim Alignment")

            for idx, (f_path, b_path) in enumerate(batch):
                col = idx % cols
                # For duplex on long edge, mirror column: 0 -> 1, 1 -> 0
                mirrored_col = (cols - 1) - col
                row = idx // cols
                x = margin_x + mirrored_col * (card_w + gap_x)
                y = a4_h - margin_y - (row + 1) * card_h - row * gap_y

                c.drawImage(str(b_path), x, y, width=card_w, height=card_h)
                draw_crop_marks(c, x, y, card_w, card_h)

            c.showPage()

        c.save()
        return output_pdf_path

    @staticmethod
    def generate_card_for_student(school, student, base_url="http://localhost:5000", template_id=None, qr_token=None):
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
            qr_token = qr_token or getattr(student, "pending_card_qr_token", None) or QRService.generate_unique_token()
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
        student.pending_card_qr_token = None

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
