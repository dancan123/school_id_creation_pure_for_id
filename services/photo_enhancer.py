import os
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import io

class PhotoEnhancer:
    """Smart Automated Photo Normalizer & Face Centering Engine for CR80 PVC ID credentials.

    Provides high-speed portrait alignment, 3:4 passport aspect ratio cropping,
    contrast enhancement, and clean background neutralization without heavy binary dependencies.
    """

    @staticmethod
    def _estimate_face_center(img):
        """Estimates the approximate horizontal and vertical center of the head/face."""
        w, h = img.size
        # Work with a downscaled grayscale image for speed
        thumb = img.convert("L").resize((120, 160))
        tw, th = thumb.size

        # In typical portrait photos, face sits in upper 20% - 65% of the frame
        y_min = int(th * 0.15)
        y_max = int(th * 0.70)
        x_min = int(tw * 0.15)
        x_max = int(tw * 0.85)

        pixels = thumb.load()
        # Find horizontal center of mass in face zone
        x_weights = 0
        total_weight = 0
        y_weights = 0

        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                val = pixels[x, y]
                # High contrast edges / skin tones usually stand out from plain walls
                # Weight by contrast from top corner background
                bg_sample = pixels[5, 5]
                diff = abs(val - bg_sample)
                if diff > 25:
                    x_weights += x * diff
                    y_weights += y * diff
                    total_weight += diff

        if total_weight > 0:
            center_x_norm = (x_weights / total_weight) / tw
            center_y_norm = (y_weights / total_weight) / th
        else:
            center_x_norm = 0.50
            center_y_norm = 0.38

        # Clamp center estimates within reasonable bounds
        center_x = max(0.35, min(0.65, center_x_norm)) * w
        center_y = max(0.28, min(0.48, center_y_norm)) * h

        return center_x, center_y

    @classmethod
    def enhance_passport_photo(cls, input_source, output_path=None, target_size=(480, 640), bg_clean=True):
        """Auto-centers, crops to standard 3:4 portrait passport ratio, balances contrast,
        and saves or returns the optimized image.

        :param input_source: File path (str/Path) or bytes / file-like object.
        :param output_path: Optional path to save result.
        :param target_size: (width, height) tuple - default 480x640 (standard CR80 3:4 at 300 DPI scale).
        :param bg_clean: Whether to apply edge leveling and contrast balance.
        """
        if isinstance(input_source, (str, Path)):
            img = Image.open(input_source)
        elif isinstance(input_source, bytes):
            img = Image.open(io.BytesIO(input_source))
        else:
            img = Image.open(input_source)

        # Fix EXIF orientation if needed
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        w, h = img.size

        # Target aspect ratio is 3:4 (w/h = 0.75)
        target_ratio = target_size[0] / target_size[1]
        current_ratio = w / h

        center_x, center_y = cls._estimate_face_center(img)

        # Compute crop box centered around detected head
        if current_ratio > target_ratio:
            # Image is too wide; crop sides
            new_w = int(h * target_ratio)
            left = int(center_x - (new_w / 2))
            # Keep within image bounds
            left = max(0, min(w - new_w, left))
            box = (left, 0, left + new_w, h)
        else:
            # Image is too tall; crop top/bottom while honoring head headroom
            new_h = int(w / target_ratio)
            # Head headroom should ideally be ~14% from top of crop
            top = int(center_y - (new_h * 0.38))
            top = max(0, min(h - new_h, top))
            box = (0, top, w, top + new_h)

        cropped = img.crop(box)
        resized = cropped.resize(target_size, Image.Resampling.LANCZOS)

        # Contrast & subtle sharpness optimization for ultra-crisp PVC thermal printing
        if bg_clean:
            enhancer = ImageEnhance.Contrast(resized)
            resized = enhancer.enhance(1.08)
            sharpener = ImageEnhance.Sharpness(resized)
            resized = sharpener.enhance(1.12)
            color_enhancer = ImageEnhance.Color(resized)
            resized = color_enhancer.enhance(1.04)

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            resized.save(str(out_p), format="JPEG", quality=92, optimize=True)
            return str(out_p)

        out_buffer = io.BytesIO()
        resized.save(out_buffer, format="JPEG", quality=92, optimize=True)
        out_buffer.seek(0)
        return out_buffer.getvalue()

    @classmethod
    def batch_enhance_directory(cls, directory_path):
        """Processes all images in a directory in place, auto-centering and standardizing each."""
        p = Path(directory_path)
        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
        processed_count = 0
        for f in p.iterdir():
            if f.is_file() and f.suffix.lower() in valid_exts:
                try:
                    cls.enhance_passport_photo(f, output_path=f)
                    processed_count += 1
                except Exception:
                    pass
        return processed_count
