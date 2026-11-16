import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

class School(db.Model):
    __tablename__ = "schools"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    code = db.Column(db.String(50), nullable=True, unique=True)
    motto = db.Column(db.String(255), nullable=True, default="Strive to Excel")
    po_box = db.Column(db.String(100), nullable=True, default="P.O. Box 123 - 00100")
    town = db.Column(db.String(100), nullable=True, default="Nairobi")
    county = db.Column(db.String(100), nullable=True, default="Nairobi")
    phone = db.Column(db.String(50), nullable=True, default="+254 700 000000")
    email = db.Column(db.String(100), nullable=True, default="info@school.ac.ke")
    website = db.Column(db.String(120), nullable=True)
    
    # Institution Profile & Classification
    institution_type = db.Column(db.String(30), nullable=False, default="school") # 'school', 'university', 'tvet', 'company', 'ngo', 'government', 'other'
    registration_number = db.Column(db.String(100), nullable=True) # Official Registration / Incorporation No.
    physical_address = db.Column(db.String(255), nullable=True)    # Campus / Building / Floor / Road
    alt_email = db.Column(db.String(120), nullable=True)
    alt_phone = db.Column(db.String(50), nullable=True)
    
    # Visual Branding & Color adjustment per school
    primary_color = db.Column(db.String(20), nullable=False, default="#1E3A8A")  # Deep blue
    secondary_color = db.Column(db.String(20), nullable=False, default="#F59E0B") # Gold / Amber
    accent_color = db.Column(db.String(20), nullable=False, default="#10B981")    # Emerald
    card_bg_color = db.Column(db.String(20), nullable=False, default="#FFFFFF")   # White
    text_color = db.Column(db.String(20), nullable=False, default="#0F172A")      # Dark slate
    enable_watermark = db.Column(db.Boolean, default=True)
    enable_smart_chip = db.Column(db.Boolean, default=True)
    
    # Media paths
    logo_filename = db.Column(db.String(255), nullable=True)
    stamp_filename = db.Column(db.String(255), nullable=True) # Official school/company rubber stamp or seal
    principal_signature_filename = db.Column(db.String(255), nullable=True)
    principal_name = db.Column(db.String(100), nullable=True, default="Principal / Headteacher")
    principal_title = db.Column(db.String(100), nullable=True, default="Principal / Head of Institution")
    
    # Dynamic Field Labels for School vs Corporate / Company Cards
    card_title = db.Column(db.String(100), nullable=True, default="STUDENT IDENTIFICATION CARD")
    id_label = db.Column(db.String(50), nullable=True, default="ADM NO")
    sub_photo_label = db.Column(db.String(50), nullable=True, default="ADM NO") # Label directly beneath passport photo
    class_label = db.Column(db.String(50), nullable=True, default="CLASS / GRADE")
    stream_label = db.Column(db.String(50), nullable=True, default="STREAM")
    upi_label = db.Column(db.String(50), nullable=True, default="NEMIS / UPI")
    
    # Extensible Configurations (JSON)
    custom_fields_json = db.Column(db.Text, nullable=True)  # JSON list of custom field definitions
    terms_clauses_json = db.Column(db.Text, nullable=True)  # JSON list of enabled/custom terms clauses
    header_config_json = db.Column(db.Text, nullable=True)  # JSON configuration for header layout
    print_settings_json = db.Column(db.Text, nullable=True) # JSON configuration for printer margins
    
    # ID Generation Rules
    academic_year = db.Column(db.String(20), nullable=False, default=str(datetime.datetime.now().year))
    card_prefix = db.Column(db.String(20), nullable=True, default="ID-")
    validity_years = db.Column(db.Integer, nullable=False, default=4)
    default_template_id = db.Column(db.Integer, nullable=True)
    
    # Back-of-card settings
    disclaimer_text = db.Column(db.Text, nullable=True, default="1. This card remains the property of the school.\n2. If found, please return to the school administration or nearest police station.\n3. The card must be carried at all times within the school premises.\n4. The card must carried anytime when on school uniform anywhere.")
    emergency_contact_phone = db.Column(db.String(50), nullable=True)
    security_notice = db.Column(db.String(255), nullable=True, default="Official institutional credential. Unlawful alteration or possession is prohibited.")
    show_security_notice = db.Column(db.Boolean, default=True)
    show_header_contacts = db.Column(db.Boolean, default=True)
    header_contact_text = db.Column(db.Text, nullable=True)  # Custom multiline header contacts override
    auto_whiten_photo = db.Column(db.Boolean, default=False)
    
    # Self-onboarding settings
    allow_self_onboarding = db.Column(db.Boolean, default=True)
    auto_approve_onboarding = db.Column(db.Boolean, default=False)
    onboarding_instructions = db.Column(db.Text, nullable=True)
    onboarding_base_url = db.Column(db.String(255), nullable=True)
    admission_number_prefix = db.Column(db.String(20), nullable=True)
    admission_number_length = db.Column(db.Integer, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Relationships
    students = db.relationship("Student", backref="school", cascade="all, delete-orphan", lazy=True)
    templates = db.relationship("IdTemplate", backref="school", cascade="all, delete-orphan", lazy=True)
    card_records = db.relationship("CardRecord", backref="school", cascade="all, delete-orphan", lazy=True)
    users = db.relationship("User", backref="school", cascade="all, delete-orphan", lazy=True)
    import_jobs = db.relationship("ImportJob", backref="school", cascade="all, delete-orphan", lazy=True)
    generation_jobs = db.relationship("GenerationJob", backref="school", cascade="all, delete-orphan", lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # ── Institution Classification Helpers ──────────────────────────────────────
    def is_school(self):
        t = (self.institution_type or "school").lower()
        return t in ["school", "primary", "secondary", "jss", "high school"]

    def is_university(self):
        t = (self.institution_type or "").lower()
        return t in ["college", "university", "tertiary"]

    def is_tvet(self):
        t = (self.institution_type or "").lower()
        return t in ["tvet", "vocational", "polytechnic", "institute"]

    def is_corporate(self):
        t = (self.institution_type or "").lower()
        return t in ["corporate", "company", "enterprise", "business", "firm"]

    def is_ngo(self):
        t = (self.institution_type or "").lower()
        return t in ["organization", "ngo", "cbo", "sacco", "society", "foundation", "church", "hospital"]

    def is_government(self):
        t = (self.institution_type or "").lower()
        return t in ["government", "ministry", "agency", "parastatal", "authority"]

    def get_institution_type_display(self):
        t = (self.institution_type or "school").lower()
        mapping = {
            "school": "Primary / Secondary School",
            "college": "College / University",
            "university": "College / University",
            "tvet": "TVET Institution",
            "company": "Company / Business",
            "corporate": "Company / Business",
            "ngo": "NGO / Community Organization",
            "organization": "NGO / Community Organization",
            "government": "Government Institution",
            "other": "Other Registered Institution"
        }
        return mapping.get(t, t.capitalize())

    def get_institution_label(self):
        if self.is_corporate():
            return "Company"
        elif self.is_ngo():
            return "Organization"
        elif self.is_university():
            return "College / University"
        elif self.is_tvet():
            return "TVET Institution"
        elif self.is_government():
            return "Government Institution"
        return "School"

    # ── Context-Aware Identity Field Labels ─────────────────────────────────────
    def get_member_label(self):
        if self.is_corporate():
            return "Employee"
        elif self.is_tvet():
            return "Trainee"
        elif self.is_ngo():
            return "Member"
        elif self.is_government():
            return "Officer"
        return "Student"

    def get_member_label_plural(self):
        if self.is_corporate():
            return "Employees"
        elif self.is_tvet():
            return "Trainees"
        elif self.is_ngo():
            return "Members"
        elif self.is_government():
            return "Officers"
        return "Students"

    def get_members_title(self):
        if self.is_corporate():
            return "Employee Records"
        elif self.is_tvet():
            return "Trainee Records"
        elif self.is_ngo():
            return "Member Records"
        elif self.is_government():
            return "Personnel Records"
        return "Student Records"

    def get_id_label(self):
        if self.id_label and self.id_label.strip():
            return self.id_label.strip()
        if self.is_corporate():
            return "EMP NO"
        elif self.is_university() or self.is_tvet():
            return "REG NO"
        elif self.is_ngo():
            return "MEMBER NO"
        elif self.is_government():
            return "SVC NO"
        return "ADM NO"

    def get_sub_photo_label(self):
        """Label placed directly below the passport picture (e.g. ADM NO: 556 or REG NO: 556)."""
        if self.sub_photo_label and self.sub_photo_label.strip():
            return self.sub_photo_label.strip()
        if self.is_corporate():
            return "EMP NO"
        elif self.is_university() or self.is_tvet() or self.is_ngo():
            return "REG NO"
        elif self.is_government():
            return "SVC NO"
        return "ADM NO"

    def get_class_label(self):
        if self.class_label and self.class_label.strip():
            return self.class_label.strip()
        if self.is_corporate():
            return "DEPARTMENT"
        elif self.is_university():
            return "FACULTY / DEPT"
        elif self.is_tvet():
            return "DEPARTMENT"
        elif self.is_ngo():
            return "CHAPTER / DEPT"
        elif self.is_government():
            return "DIRECTORATE"
        return "CLASS / GRADE"

    def get_stream_label(self):
        if self.stream_label and self.stream_label.strip():
            return self.stream_label.strip()
        if self.is_corporate():
            return "DESIGNATION / ROLE"
        elif self.is_university():
            return "COURSE / PROGRAMME"
        elif self.is_tvet():
            return "TRADE / LEVEL"
        elif self.is_ngo():
            return "ROLE / CATEGORY"
        elif self.is_government():
            return "RANK / STATION"
        return "STREAM"

    def get_academic_year_label(self):
        if self.is_corporate() or self.is_government():
            return "FISCAL / ISSUE YEAR"
        elif self.is_ngo():
            return "MEMBERSHIP YEAR"
        return "ACADEMIC YEAR"

    def get_guardian_label(self):
        if self.is_school():
            return "PARENT / GUARDIAN"
        return "EMERGENCY CONTACT"

    def get_upi_label(self):
        if self.upi_label and self.upi_label.strip():
            return self.upi_label.strip()
        if self.is_school():
            return "NEMIS / UPI"
        elif self.is_university() or self.is_tvet():
            return "KUCCPS / NEMIS"
        return "NATIONAL ID / SSN"

    def get_card_title(self):
        if self.card_title and self.card_title.strip():
            return self.card_title.strip()
        if self.is_corporate():
            return "EMPLOYEE IDENTIFICATION CARD"
        elif self.is_university():
            return "UNIVERSITY IDENTIFICATION CARD"
        elif self.is_tvet():
            return "TVET TRAINEE IDENTIFICATION CARD"
        elif self.is_ngo():
            return "MEMBERSHIP IDENTIFICATION CARD"
        elif self.is_government():
            return "OFFICIAL IDENTIFICATION CREDENTIAL"
        return "STUDENT IDENTIFICATION CARD"

    def get_signatory_title(self):
        if self.principal_title and self.principal_title.strip():
            return self.principal_title.strip()
        if self.is_corporate():
            return "Managing Director / CEO"
        elif self.is_university():
            return "Vice Chancellor / Registrar"
        elif self.is_tvet():
            return "Principal / Director"
        elif self.is_ngo():
            return "Executive Director / Secretary General"
        elif self.is_government():
            return "Director General / Authorized Signatory"
        return "Principal / Head of Institution"

    def get_disclaimer_lines(self):
        """Returns the list of active terms & conditions clauses for card reverse."""
        if self.terms_clauses_json:
            try:
                import json
                clauses = json.loads(self.terms_clauses_json)
                if isinstance(clauses, list) and clauses:
                    return [c.strip() for c in clauses if isinstance(c, str) and c.strip()]
            except Exception:
                pass
        
        # Fall back to disclaimer_text
        if self.disclaimer_text:
            lines = [ln.strip() for ln in self.disclaimer_text.replace("\r", "").split("\n") if ln.strip()]
            if lines:
                return lines

        # Default institutional 4 rules
        inst_noun = "company" if self.is_corporate() else ("organization" if self.is_ngo() else "school")
        return [
            f"1. This card remains the property of the {inst_noun}.",
            f"2. If found, please return to the {inst_noun} administration or nearest police station.",
            f"3. The card must be carried at all times within the premises.",
            f"4. The card must carried anytime when on official duty or uniform."
        ]

    def get_header_contact_lines(self):
        """Returns the list of contact lines to display in the card header.
        If custom header_contact_text is defined in settings, splits and returns those lines.
        Otherwise, builds structured lines with prefixes (P.O. Box, Website, Email, Mobile No)."""
        import re
        if getattr(self, "header_contact_text", None) and self.header_contact_text.strip():
            lines = [ln.strip() for ln in self.header_contact_text.replace("\r", "").split("\n") if ln.strip()]
            if lines:
                return lines

        lines = []
        # Line 1: Postal & Town / County
        addr_parts = []
        if self.po_box and self.po_box.strip():
            addr_parts.append(self.po_box.strip())
        town_county = f"{self.town}, {self.county}" if self.town and self.county else (self.town or self.county or "")
        if town_county.strip():
            addr_parts.append(town_county.strip())
        if addr_parts:
            lines.append(" • ".join(addr_parts))

        # Line 2: Website (e.g. Website: high.ac.ke)
        if self.website and self.website.strip():
            web_clean = re.sub(r"^https?://", "", self.website.strip()).rstrip("/")
            lines.append(f"Website: {web_clean}")

        # Line 3: Email (e.g. Email: info@high.ac.ke)
        if self.email and self.email.strip():
            lines.append(f"Email: {self.email.strip()}")

        # Line 4: Mobile / Phone (e.g. Mobile No: +254 722 000000)
        phone_val = (self.phone or self.alt_phone or "").strip()
        if phone_val:
            lines.append(f"Mobile No: {phone_val}")

        return lines

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "motto": self.motto,
            "institution_type": self.institution_type,
            "registration_number": self.registration_number,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "academic_year": self.academic_year,
            "phone": self.phone,
            "town": self.town,
            "county": self.county,
            "logo_filename": self.logo_filename,
            "stamp_filename": self.stamp_filename,
            "principal_title": self.get_signatory_title(),
            "card_title": self.get_card_title()
        }


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="admin") # superadmin, admin, operator, auditor
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_number = db.Column(db.String(50), nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    first_name = db.Column(db.String(60), nullable=True)
    last_name = db.Column(db.String(60), nullable=True)

    # ── Curriculum & Class ──────────────────────────────────────────────────────
    # curriculum_type: 'CBC' (new Kenya system) or '844' (old 8-4-4 system)
    curriculum_type = db.Column(db.String(10), nullable=False, default="CBC", index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)   # e.g. "Grade 7", "JSS 1", "Form 1"
    stream_name = db.Column(db.String(50), nullable=True, index=True)   # e.g. "East", "Blue"
    gender = db.Column(db.String(20), nullable=True)
    dob = db.Column(db.String(20), nullable=True)
    academic_year = db.Column(db.String(20), nullable=False, default=str(datetime.datetime.now().year))

    parent_name = db.Column(db.String(100), nullable=True)
    parent_phone = db.Column(db.String(50), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    house_or_dorm = db.Column(db.String(50), nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)
    photo_cropped_filename = db.Column(db.String(255), nullable=True)
    signature_filename = db.Column(db.String(255), nullable=True)
    nemis_upi = db.Column(db.String(50), nullable=True)

    # ── Card & Enrolment Status ─────────────────────────────────────────────────
    card_status = db.Column(db.String(30), nullable=False, default="pending")
    card_number = db.Column(db.String(50), nullable=True)
    pending_card_qr_token = db.Column(db.String(64), nullable=True, unique=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    # enrolment_status tracks self-service intake pipeline:
    # 'active' = staff-added (default), 'self_pending' = submitted via portal,
    # 'verified' = approved by admin, 'rejected' = rejected
    enrolment_status = db.Column(db.String(20), nullable=False, default="active", index=True)
    self_enrolment_token = db.Column(db.String(64), nullable=True, unique=True)  # for edit link

    is_archived = db.Column(db.Boolean, default=False)
    custom_data_json = db.Column(db.Text, nullable=True) # JSON dict storing extensible custom field values
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    card_records = db.relationship("CardRecord", backref="student", cascade="all, delete-orphan", lazy=True)
    verification_tokens = db.relationship("QRVerificationToken", backref="student", cascade="all, delete-orphan", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("school_id", "admission_number", name="uq_school_student_admission"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # ── Universal Multi-Institution Identity Aliases ────────────────────────────
    @property
    def employee_number(self):
        return self.admission_number

    @employee_number.setter
    def employee_number(self, val):
        self.admission_number = val

    @property
    def membership_number(self):
        return self.admission_number

    @membership_number.setter
    def membership_number(self, val):
        self.admission_number = val

    @property
    def department(self):
        return self.class_name

    @department.setter
    def department(self, val):
        self.class_name = val

    @property
    def designation(self):
        return self.stream_name

    @designation.setter
    def designation(self, val):
        self.stream_name = val

    def get_custom_data(self):
        if not self.custom_data_json:
            return {}
        try:
            import json
            data = json.loads(self.custom_data_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_custom_data(self, key_or_dict, value=None):
        import json
        current = self.get_custom_data()
        if isinstance(key_or_dict, dict):
            current.update(key_or_dict)
        elif isinstance(key_or_dict, str):
            current[key_or_dict] = value
        self.custom_data_json = json.dumps(current)


# ── Self-Service Student Enrolment Portal ────────────────────────────────────
class SelfEnrolment(db.Model):
    """Holds intake submissions from the public /onboard/<school_code> or /enrol/<school_code> portal.
    
    Students fill in their details with live camera/cropping and digital signature tools; an admin reviews and either:
    - approves  → creates/updates a Student row and optionally generates their ID card instantly
    - rejects   → marks this record rejected with an explanatory note
    """
    __tablename__ = "self_enrolments"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Minimum required for ID generation ──────────────────────────────────
    full_name = db.Column(db.String(150), nullable=False)
    admission_number = db.Column(db.String(50), nullable=False)
    curriculum_type = db.Column(db.String(10), nullable=False, default="CBC")
    class_name = db.Column(db.String(50), nullable=False)     # e.g. Grade 7, JSS 2, Form 3
    stream_name = db.Column(db.String(50), nullable=True)
    academic_year = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(20), nullable=True)
    dob = db.Column(db.String(20), nullable=True)

    # Submission & Identification details
    nemis_upi = db.Column(db.String(50), nullable=True)
    parent_name = db.Column(db.String(100), nullable=True)
    parent_phone = db.Column(db.String(50), nullable=True)
    emergency_relationship = db.Column(db.String(50), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    house_or_dorm = db.Column(db.String(60), nullable=True)
    medical_notes = db.Column(db.String(255), nullable=True)

    # Photo & signature uploaded/captured by the student
    photo_filename = db.Column(db.String(255), nullable=True)
    signature_filename = db.Column(db.String(255), nullable=True)
    submission_token = db.Column(db.String(64), nullable=True, unique=True, index=True)
    card_qr_token = db.Column(db.String(64), nullable=True, unique=True)
    resubmission_count = db.Column(db.Integer, nullable=False, default=0)

    # Pipeline state
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # pending | approved | rejected
    rejection_reason = db.Column(db.String(500), nullable=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Link back to created student record on approval
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="SET NULL"), nullable=True)

    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    ip_address = db.Column(db.String(50), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class AdmissionAllowlist(db.Model):
    """School-approved admission numbers permitted to use public onboarding once."""
    __tablename__ = "admission_allowlist"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_number = db.Column(db.String(50), nullable=False)
    qr_token = db.Column(db.String(64), nullable=False, unique=True)
    source = db.Column(db.String(20), nullable=False, default="manual")
    allocation_batch_id = db.Column(db.String(36), nullable=True, index=True)
    current_enrolment_id = db.Column(db.Integer, db.ForeignKey("self_enrolments.id", ondelete="SET NULL"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("school_id", "admission_number", name="uq_school_allowlist_admission"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class IdTemplate(db.Model):
    __tablename__ = "id_templates"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    
    orientation = db.Column(db.String(20), nullable=False, default="landscape")
    width_mm = db.Column(db.Float, nullable=False, default=85.60)
    height_mm = db.Column(db.Float, nullable=False, default=53.98)
    
    layout_config = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class CardRecord(db.Model):
    __tablename__ = "card_records"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("id_templates.id", ondelete="SET NULL"), nullable=True)
    
    card_number = db.Column(db.String(50), nullable=False, index=True)
    qr_token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    
    issue_date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    expiry_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="active")
    
    front_image_filename = db.Column(db.String(255), nullable=True)
    back_image_filename = db.Column(db.String(255), nullable=True)
    single_pdf_filename = db.Column(db.String(255), nullable=True)
    
    print_status = db.Column(db.String(30), nullable=False, default="pending")
    printed_at = db.Column(db.DateTime, nullable=True)
    print_count = db.Column(db.Integer, default=0)
    reprint_reason = db.Column(db.String(255), nullable=True)

    # Renewal Tracking (for single and bulk renewals)
    renewal_count = db.Column(db.Integer, default=0)
    last_renewed_at = db.Column(db.DateTime, nullable=True)
    renewal_notes = db.Column(db.String(255), nullable=True)

    generation_batch_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class QRVerificationToken(db.Model):
    __tablename__ = "qr_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    card_record_id = db.Column(db.Integer, db.ForeignKey("card_records.id", ondelete="CASCADE"), nullable=True)
    
    is_valid = db.Column(db.Boolean, default=True)
    scan_count = db.Column(db.Integer, default=0)
    last_scanned_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ImportJob(db.Model):
    __tablename__ = "import_jobs"

    id = db.Column(db.String(64), primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    total_records = db.Column(db.Integer, default=0)
    valid_records = db.Column(db.Integer, default=0)
    invalid_records = db.Column(db.Integer, default=0)
    imported_records = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="pending")
    error_summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class GenerationJob(db.Model):
    __tablename__ = "generation_jobs"

    id = db.Column(db.String(64), primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    template_id = db.Column(db.Integer, nullable=True)
    target_scope = db.Column(db.String(100), default="all")
    total_count = db.Column(db.Integer, default=0)
    processed_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="processing")
    pdf_filename = db.Column(db.String(255), nullable=True)
    print_format = db.Column(db.String(50), default="cr80_single")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ── Universal Multi-Institution Platform Aliases ────────────────────────────
Institution = School
Member = Student
