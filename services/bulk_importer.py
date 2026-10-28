import os
import csv
import zipfile
import shutil
import re
from pathlib import Path
import openpyxl
from config import Config
from extensions import db
from models import Student

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def clean_str(val):
    if val is None:
        return ""
    return str(val).strip()

def normalize_adm(val):
    """Normalize admission number for robust matching (e.g. 'ADM-001' -> '001', 'adm/001' -> '001')."""
    s = clean_str(val).upper()
    return re.sub(r"[^A-Z0-9]", "", s)

class BulkImporter:
    @staticmethod
    def generate_sample_excel(output_path):
        """Generates a professional sample Excel template with Kenyan school headers and sample rows."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"

        headers = [
            "Admission Number",
            "Full Name",
            "Class",
            "Stream",
            "Gender",
            "Date of Birth (YYYY-MM-DD)",
            "Parent Phone",
            "Blood Group",
            "House/Dorm"
        ]
        ws.append(headers)

        # Style header
        header_fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = openpyxl.styles.Font(color="FFFFFF", bold=True)
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = max(len(header) + 4, 16)

        # Sample data
        samples = [
            ["1001", "Brian Kiprop", "Form 1", "East", "Male", "2010-04-12", "0712345678", "O+", "Simba"],
            ["1002", "Faith Wanjiku", "Form 1", "West", "Female", "2010-09-21", "0723456789", "A+", "Chui"],
            ["1003", "Emmanuel Otieno", "Form 2", "North", "Male", "2009-02-15", "0734567890", "B+", "Kifaru"],
            ["1004", "Mercy Chebet", "Form 2", "South", "Female", "2009-11-05", "0745678901", "AB+", "Twiga"],
            ["1005", "Kevin Mutua", "Form 3", "East", "Male", "2008-07-30", "0756789012", "O-", "Nyati"],
        ]
        for row in samples:
            ws.append(row)

        wb.save(output_path)
        return output_path

    @staticmethod
    def extract_zip_photos(zip_path, target_dir):
        """Extracts student photos from a zip file into target directory and returns map of normalized_name -> filename."""
        extracted_map = {}
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                filename = os.path.basename(member.filename)
                if not filename or filename.startswith(".") or filename.startswith("__MACOSX"):
                    continue
                ext = Path(filename).suffix.lower()
                if ext in ALLOWED_IMAGE_EXTS:
                    # Extract file
                    out_path = target_dir / filename
                    with zf.open(member) as source, open(out_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                    base_stem = Path(filename).stem
                    norm_stem = normalize_adm(base_stem)
                    extracted_map[norm_stem] = filename
                    # also map full raw stem
                    extracted_map[clean_str(base_stem).upper()] = filename

        return extracted_map

    @staticmethod
    def read_records(file_path):
        """Reads rows from .xlsx, .xls, or .csv file and returns (headers, rows_as_dicts)."""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        rows = []
        headers = []

        if ext == ".csv":
            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                all_lines = [row for row in reader if any(cell.strip() for cell in row)]
                if all_lines:
                    headers = [c.strip() for c in all_lines[0]]
                    for row_idx, r in enumerate(all_lines[1:], start=2):
                        row_dict = {headers[i] if i < len(headers) else f"col_{i}": (r[i].strip() if i < len(r) else "") for i in range(len(r))}
                        row_dict["_row_number"] = row_idx
                        rows.append(row_dict)
        else:
            # Excel
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            first = True
            for row_idx, r in enumerate(ws.iter_rows(values_only=True), start=1):
                if first:
                    headers = [clean_str(c) for c in r if clean_str(c)]
                    first = False
                else:
                    if not any(r):
                        continue
                    row_dict = {}
                    for i, h in enumerate(headers):
                        val = r[i] if i < len(r) else ""
                        row_dict[h] = clean_str(val)
                    row_dict["_row_number"] = row_idx
                    rows.append(row_dict)

        return headers, rows

    @staticmethod
    def auto_detect_mapping(headers):
        """Auto detects column mapping for common Kenyan spreadsheet variations."""
        mapping = {}
        patterns = {
            "admission_number": [r"adm.*no", r"admission.*no", r"adm_no", r"admission", r"reg.*no", r"student.*id"],
            "full_name": [r"full.*name", r"student.*name", r"name", r"names"],
            "class_name": [r"class", r"form", r"grade", r"standard"],
            "stream_name": [r"stream", r"section", r"track"],
            "gender": [r"gender", r"sex"],
            "dob": [r"dob", r"date.*of.*birth", r"birth.*date"],
            "parent_phone": [r"parent.*phone", r"phone", r"guardian.*phone", r"mobile", r"contact"],
            "blood_group": [r"blood.*group", r"blood"],
            "house_or_dorm": [r"house", r"dorm", r"dormitory"]
        }

        for field, pat_list in patterns.items():
            for h in headers:
                h_clean = h.lower().replace("_", " ").replace("-", " ")
                if any(re.search(p, h_clean) for p in pat_list):
                    mapping[field] = h
                    break
        return mapping

    @staticmethod
    def validate_records(school_id, rows, mapping, photo_map=None, academic_year="2026"):
        """Validates all rows, checks duplicates in DB and file, matches photos.
           Returns: (valid_records, invalid_records, errors_list)
        """
        valid_records = []
        invalid_records = []
        errors_list = []

        # Existing admission numbers in this school
        existing_adms = {
            clean_str(adm).upper(): True
            for (adm,) in db.session.query(Student.admission_number).filter_by(school_id=school_id).all()
        }

        file_seen_adms = {}

        adm_col = mapping.get("admission_number")
        name_col = mapping.get("full_name")
        class_col = mapping.get("class_name")
        stream_col = mapping.get("stream_name")
        gender_col = mapping.get("gender")
        dob_col = mapping.get("dob")
        phone_col = mapping.get("parent_phone")
        blood_col = mapping.get("blood_group")
        house_col = mapping.get("house_or_dorm")

        for r in rows:
            row_no = r.get("_row_number", "?")
            adm_val = clean_str(r.get(adm_col, ""))
            name_val = clean_str(r.get(name_col, ""))
            class_val = clean_str(r.get(class_col, ""))
            stream_val = clean_str(r.get(stream_col, "")) if stream_col else ""
            gender_val = clean_str(r.get(gender_col, "")) if gender_col else ""
            dob_val = clean_str(r.get(dob_col, "")) if dob_col else ""
            phone_val = clean_str(r.get(phone_col, "")) if phone_col else ""
            blood_val = clean_str(r.get(blood_col, "")) if blood_col else ""
            house_val = clean_str(r.get(house_col, "")) if house_col else ""

            row_errors = []

            if not adm_val:
                row_errors.append("Missing Admission Number.")
            if not name_val:
                row_errors.append("Missing Student Full Name.")
            if not class_val:
                row_errors.append("Missing Class/Form.")

            adm_upper = adm_val.upper()
            if adm_val:
                if adm_upper in file_seen_adms:
                    row_errors.append(f"Duplicate Admission Number in file (already at row {file_seen_adms[adm_upper]}).")
                else:
                    file_seen_adms[adm_upper] = row_no

                if adm_upper in existing_adms:
                    row_errors.append(f"Admission Number '{adm_val}' already registered in this school.")

            # Photo matching
            matched_photo = None
            if photo_map and adm_val:
                norm_adm = normalize_adm(adm_val)
                matched_photo = photo_map.get(norm_adm) or photo_map.get(adm_upper)

            record_item = {
                "row_number": row_no,
                "admission_number": adm_val,
                "full_name": name_val,
                "class_name": class_val,
                "stream_name": stream_val,
                "gender": gender_val,
                "dob": dob_val,
                "parent_phone": phone_val,
                "blood_group": blood_val,
                "house_or_dorm": house_val,
                "academic_year": academic_year,
                "photo_filename": matched_photo,
                "has_photo": bool(matched_photo),
                "errors": row_errors,
                "is_valid": len(row_errors) == 0
            }

            if row_errors:
                invalid_records.append(record_item)
                for err in row_errors:
                    errors_list.append({
                        "row": row_no,
                        "admission_number": adm_val or "BLANK",
                        "name": name_val or "BLANK",
                        "error": err
                    })
            else:
                valid_records.append(record_item)

        return valid_records, invalid_records, errors_list

    @staticmethod
    def commit_valid_records(school_id, valid_records):
        """Inserts all validated records within a database transaction."""
        inserted_count = 0
        students_to_add = []

        for rec in valid_records:
            student = Student(
                school_id=school_id,
                admission_number=rec["admission_number"],
                full_name=rec["full_name"],
                class_name=rec["class_name"],
                stream_name=rec["stream_name"],
                gender=rec["gender"],
                dob=rec["dob"],
                parent_phone=rec["parent_phone"],
                blood_group=rec["blood_group"],
                house_or_dorm=rec["house_or_dorm"],
                academic_year=rec["academic_year"],
                photo_filename=rec["photo_filename"],
                card_status="pending"
            )
            students_to_add.append(student)

        db.session.bulk_save_objects(students_to_add)
        db.session.commit()
        return len(students_to_add)
