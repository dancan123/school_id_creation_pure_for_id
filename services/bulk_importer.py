import os
import csv
import zipfile
import shutil
import re
from pathlib import Path
import openpyxl
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
    def generate_sample_excel(output_path, school=None):
        """Generates a professional sample Excel template adapted dynamically to the institution type."""
        wb = openpyxl.Workbook()
        ws = wb.active

        if school and school.is_corporate():
            ws.title = "Employees"
            headers = [
                "Employee ID",
                "Full Name",
                "Department",
                "Job Title / Role",
                "Gender",
                "Date of Birth (YYYY-MM-DD)",
                "Phone Number",
                "Blood Group",
                "Station / Branch"
            ]
            samples = [
                ["EMP-1001", "David Maina", "Engineering", "Senior Software Engineer", "Male", "1990-04-12", "0712345678", "O+", "Nairobi HQ"],
                ["EMP-1002", "Grace Achieng", "Human Resources", "HR Manager", "Female", "1992-09-21", "0723456789", "A+", "Nairobi HQ"],
                ["EMP-1003", "Emmanuel Otieno", "Operations", "Logistics Officer", "Male", "1988-02-15", "0734567890", "B+", "Mombasa Branch"],
                ["EMP-1004", "Faith Muthoni", "Finance", "Senior Accountant", "Female", "1994-11-05", "0745678901", "AB+", "Nairobi HQ"],
                ["EMP-1005", "Kevin Mutua", "Marketing", "Brand Specialist", "Male", "1991-07-30", "0756789012", "O-", "Kisumu Branch"],
            ]
        elif school and (school.is_university() or school.is_tvet()):
            ws.title = school.get_member_label_plural() or "Students"
            headers = [
                school.get_id_label() or "Registration Number",
                "Full Name",
                school.get_class_label().title() if school.get_class_label() else "Faculty / Department",
                school.get_stream_label().title() if school.get_stream_label() else "Course / Programme",
                "Gender",
                "Date of Birth (YYYY-MM-DD)",
                "Phone Number",
                "Blood Group",
                "Campus"
            ]
            samples = [
                ["CIT/001/2024", "Brian Kiprop", "School of Computing", "BSc Computer Science", "Male", "2003-04-12", "0712345678", "O+", "Main Campus"],
                ["BBA/014/2024", "Faith Wanjiku", "School of Business", "Bachelor of Commerce", "Female", "2004-09-21", "0723456789", "A+", "Town Campus"],
                ["ENG/088/2023", "Emmanuel Otieno", "School of Engineering", "BSc Civil Engineering", "Male", "2002-02-15", "0734567890", "B+", "Main Campus"],
                ["MED/022/2024", "Mercy Chebet", "Health Sciences", "BSc Nursing", "Female", "2003-11-05", "0745678901", "AB+", "Medical Complex"],
                ["LAW/007/2023", "Kevin Mutua", "School of Law", "Bachelor of Laws", "Male", "2002-07-30", "0756789012", "O-", "Parklands Campus"],
            ]
        elif school and (school.is_ngo() or school.is_government()):
            ws.title = school.get_member_label_plural() or "Members"
            headers = [
                school.get_id_label() or "Member ID",
                "Full Name",
                school.get_class_label().title() if school.get_class_label() else "Department / Chapter",
                school.get_stream_label().title() if school.get_stream_label() else "Role / Position",
                "Gender",
                "Date of Birth (YYYY-MM-DD)",
                "Phone Number",
                "Blood Group",
                "Station / Station"
            ]
            samples = [
                ["MEM-1001", "Alice Nduta", "Community Outreach", "Field Officer", "Female", "1991-05-14", "0712345678", "O+", "Nairobi Central"],
                ["MEM-1002", "Dennis Barasa", "Programmes", "Project Lead", "Male", "1987-10-22", "0723456789", "A+", "Western Hub"],
                ["MEM-1003", "Cynthia Moraa", "Advocacy", "Communications Officer", "Female", "1993-01-30", "0734567890", "B+", "Coast Region"],
                ["MEM-1004", "Geoffrey Kibet", "Operations", "Regional Coordinator", "Male", "1985-08-19", "0745678901", "AB+", "Rift Valley"],
            ]
        else:
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
            samples = [
                ["1001", "Brian Kiprop", "Form 1", "East", "Male", "2010-04-12", "0712345678", "O+", "Simba"],
                ["1002", "Faith Wanjiku", "Form 1", "West", "Female", "2010-09-21", "0723456789", "A+", "Chui"],
                ["1003", "Emmanuel Otieno", "Form 2", "North", "Male", "2009-02-15", "0734567890", "B+", "Kifaru"],
                ["1004", "Mercy Chebet", "Form 2", "South", "Female", "2009-11-05", "0745678901", "AB+", "Twiga"],
                ["1005", "Kevin Mutua", "Form 3", "East", "Male", "2008-07-30", "0756789012", "O-", "Nyati"],
            ]

        ws.append(headers)

        # Style header
        primary_hex = "1E3A8A"
        if school and getattr(school, "primary_color", None):
            cleaned_hex = school.primary_color.lstrip("#").upper()
            if len(cleaned_hex) == 6:
                primary_hex = cleaned_hex

        header_fill = openpyxl.styles.PatternFill(start_color=primary_hex, end_color=primary_hex, fill_type="solid")
        header_font = openpyxl.styles.Font(color="FFFFFF", bold=True)
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = max(len(header) + 4, 16)

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

                    # Automated Smart Headshot Centering & 3:4 Normalization
                    try:
                        from services.photo_enhancer import PhotoEnhancer
                        PhotoEnhancer.enhance_passport_photo(out_path, output_path=out_path)
                    except Exception:
                        pass

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
        """Auto detects column mapping for schools, universities, companies, and organizations."""
        mapping = {}
        patterns = {
            "admission_number": [
                r"adm.*no", r"admission.*no", r"adm_no", r"admission", r"reg.*no", r"registration.*no",
                r"student.*id", r"emp.*no", r"employee.*no", r"employee.*id", r"staff.*no", r"staff.*id",
                r"payroll.*no", r"member.*no", r"member.*id", r"officer.*id", r"id.*no", r"national.*id",
                r"serial.*no", r"matric.*no", r"identifier"
            ],
            "full_name": [
                r"full.*name", r"student.*name", r"employee.*name", r"staff.*name", r"member.*name",
                r"name", r"names", r"person.*name"
            ],
            "class_name": [
                r"class", r"form", r"grade", r"standard", r"department", r"dept", r"faculty",
                r"unit", r"division", r"branch", r"cohort", r"team", r"directorate"
            ],
            "stream_name": [
                r"stream", r"section", r"track", r"job.*title", r"title", r"position", r"role",
                r"designation", r"course", r"programme", r"cadre", r"rank"
            ],
            "gender": [r"gender", r"sex"],
            "dob": [r"dob", r"date.*of.*birth", r"birth.*date", r"birthdate"],
            "parent_phone": [
                r"parent.*phone", r"phone", r"telephone", r"mobile", r"contact", r"emergency.*contact",
                r"guardian.*phone", r"cell", r"phone.*no"
            ],
            "blood_group": [r"blood.*group", r"blood.*type", r"blood"],
            "house_or_dorm": [
                r"house", r"dorm", r"dormitory", r"station", r"campus", r"building", r"office",
                r"location", r"zone"
            ]
        }

        for field, pat_list in patterns.items():
            for h in headers:
                h_clean = h.lower().replace("_", " ").replace("-", " ").strip()
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
