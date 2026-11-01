-- Complete SQLite Schema for Kenyan School ID Card Generation System
-- Multi-school support with per-school customizable colors and settings

CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(150) NOT NULL UNIQUE,
    code VARCHAR(50) UNIQUE,
    motto VARCHAR(255) DEFAULT 'Strive to Excel',
    po_box VARCHAR(100) DEFAULT 'P.O. Box 123 - 00100',
    town VARCHAR(100) DEFAULT 'Nairobi',
    county VARCHAR(100) DEFAULT 'Nairobi',
    phone VARCHAR(50) DEFAULT '+254 700 000000',
    email VARCHAR(100) DEFAULT 'info@school.ac.ke',
    website VARCHAR(120),
    primary_color VARCHAR(20) NOT NULL DEFAULT '#1E3A8A',
    secondary_color VARCHAR(20) NOT NULL DEFAULT '#F59E0B',
    accent_color VARCHAR(20) NOT NULL DEFAULT '#10B981',
    card_bg_color VARCHAR(20) NOT NULL DEFAULT '#FFFFFF',
    text_color VARCHAR(20) NOT NULL DEFAULT '#0F172A',
    logo_filename VARCHAR(255),
    principal_signature_filename VARCHAR(255),
    principal_name VARCHAR(100) DEFAULT 'Principal / Headteacher',
    academic_year VARCHAR(20) NOT NULL DEFAULT '2026',
    card_prefix VARCHAR(20) DEFAULT 'ID-',
    validity_years INTEGER NOT NULL DEFAULT 4,
    default_template_id INTEGER,
    disclaimer_text TEXT DEFAULT '1. This card remains the property of the school.\n2. If found, please return to the school administration or nearest police station.\n3. The card must be carried at all times within the school premises.',
    emergency_contact_phone VARCHAR(50),
    allow_self_onboarding BOOLEAN DEFAULT 1,
    auto_approve_onboarding BOOLEAN DEFAULT 0,
    onboarding_instructions TEXT,
    onboarding_base_url VARCHAR(255),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'admin',
    school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    admission_number VARCHAR(50) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    first_name VARCHAR(60),
    last_name VARCHAR(60),
    class_name VARCHAR(50) NOT NULL,
    stream_name VARCHAR(50),
    gender VARCHAR(20),
    dob VARCHAR(20),
    academic_year VARCHAR(20) NOT NULL DEFAULT '2026',
    parent_name VARCHAR(100),
    parent_phone VARCHAR(50),
    blood_group VARCHAR(10),
    house_or_dorm VARCHAR(50),
    photo_filename VARCHAR(255),
    photo_cropped_filename VARCHAR(255),
    card_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    card_number VARCHAR(50),
    issue_date DATE,
    expiry_date DATE,
    is_archived BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_school_student_admission UNIQUE (school_id, admission_number)
);

CREATE INDEX IF NOT EXISTS idx_student_school ON students(school_id);
CREATE INDEX IF NOT EXISTS idx_student_adm ON students(admission_number);
CREATE INDEX IF NOT EXISTS idx_student_class ON students(class_name);
CREATE INDEX IF NOT EXISTS idx_student_stream ON students(stream_name);

CREATE TABLE IF NOT EXISTS id_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER REFERENCES schools(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_default BOOLEAN DEFAULT 0,
    orientation VARCHAR(20) NOT NULL DEFAULT 'landscape',
    width_mm FLOAT NOT NULL DEFAULT 85.60,
    height_mm FLOAT NOT NULL DEFAULT 53.98,
    layout_config TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS card_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES id_templates(id) ON DELETE SET NULL,
    card_number VARCHAR(50) NOT NULL,
    qr_token VARCHAR(64) NOT NULL UNIQUE,
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    front_image_filename VARCHAR(255),
    back_image_filename VARCHAR(255),
    single_pdf_filename VARCHAR(255),
    print_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    printed_at TIMESTAMP,
    print_count INTEGER DEFAULT 0,
    reprint_reason VARCHAR(255),
    generation_batch_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_card_school ON card_records(school_id);
CREATE INDEX IF NOT EXISTS idx_card_student ON card_records(student_id);
CREATE INDEX IF NOT EXISTS idx_card_token ON card_records(qr_token);

CREATE TABLE IF NOT EXISTS qr_verification_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token VARCHAR(64) NOT NULL UNIQUE,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    card_record_id INTEGER REFERENCES card_records(id) ON DELETE CASCADE,
    is_valid BOOLEAN DEFAULT 1,
    scan_count INTEGER DEFAULT 0,
    last_scanned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id VARCHAR(64) PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    total_records INTEGER DEFAULT 0,
    valid_records INTEGER DEFAULT 0,
    invalid_records INTEGER DEFAULT 0,
    imported_records INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'pending',
    error_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id VARCHAR(64) PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    template_id INTEGER,
    target_scope VARCHAR(100) DEFAULT 'all',
    total_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'processing',
    pdf_filename VARCHAR(255),
    print_format VARCHAR(50) DEFAULT 'cr80_single',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER,
    user_id INTEGER,
    username VARCHAR(80),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT,
    description VARCHAR(255)
);
