"""
Database schema migration for self-onboarding enhancements.
Adds missing columns to SQLite database safely.
"""
import sqlite3
from pathlib import Path
from config import Config

def run_migration(db_path=None, quiet=True):
    if db_path is None:
        db_path = Config.STORAGE_DIR / "school_id_system.db"
    
    db_path = Path(db_path)
    if not db_path.exists():
        if not quiet:
            print(f"Database at {db_path} does not exist yet. Will be created by SQLAlchemy.")
        return

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Fast pre-check: if latest indicator columns exist, skip full migration sweep
    try:
        cur.execute("PRAGMA table_info(schools)")
        school_cols = {row[1] for row in cur.fetchall()}
        cur.execute("PRAGMA table_info(self_enrolments)")
        enrol_cols = {row[1] for row in cur.fetchall()}
        cur.execute("PRAGMA table_info(students)")
        student_cols = {row[1] for row in cur.fetchall()}
        if ("enable_watermark" in school_cols and
            "onboarding_base_url" in school_cols and
                "submission_token" in enrol_cols and
                "card_qr_token" in enrol_cols and
            "resubmission_count" in enrol_cols and
            "pending_card_qr_token" in student_cols):
            conn.close()
            return
    except Exception:
        pass

    # Tables and new columns to ensure exist
    migrations = {
        "schools": [
            ("allow_self_onboarding", "BOOLEAN DEFAULT 1"),
            ("auto_approve_onboarding", "BOOLEAN DEFAULT 0"),
            ("onboarding_instructions", "TEXT"),
            ("onboarding_base_url", "VARCHAR(255)"),
            ("institution_type", "VARCHAR(30) DEFAULT 'school'"),
            ("stamp_filename", "VARCHAR(255)"),
            ("principal_title", "VARCHAR(100) DEFAULT 'Principal / Head of Institution'"),
            ("card_title", "VARCHAR(100) DEFAULT 'STUDENT IDENTIFICATION CARD'"),
            ("id_label", "VARCHAR(50) DEFAULT 'ADM NO'"),
            ("class_label", "VARCHAR(50) DEFAULT 'CLASS / GRADE'"),
            ("stream_label", "VARCHAR(50) DEFAULT 'STREAM'"),
            ("upi_label", "VARCHAR(50) DEFAULT 'NEMIS / UPI'"),
            ("enable_watermark", "BOOLEAN DEFAULT 1"),
        ],
        "students": [
            ("signature_filename", "TEXT"),
            ("nemis_upi", "TEXT"),
            ("pending_card_qr_token", "VARCHAR(64)"),
        ],
        "card_records": [
            ("renewal_count", "INTEGER DEFAULT 0"),
            ("last_renewed_at", "DATETIME"),
            ("renewal_notes", "VARCHAR(255)"),
        ],
        "self_enrolments": [
            ("nemis_upi", "TEXT"),
            ("emergency_relationship", "TEXT"),
            ("house_or_dorm", "TEXT"),
            ("medical_notes", "TEXT"),
            ("signature_filename", "TEXT"),
            ("submission_token", "TEXT"),
            ("card_qr_token", "VARCHAR(64)"),
            ("resubmission_count", "INTEGER DEFAULT 0"),
        ]
    }

    for table, columns in migrations.items():
        try:
            cur.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cur.fetchall()}
            for col_name, col_type in columns:
                if col_name not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    if not quiet:
                        print(f"Added column {table}.{col_name}")
                else:
                    if not quiet:
                        print(f"Column {table}.{col_name} already exists.")
        except Exception as e:
            if not quiet:
                print(f"Error inspecting/migrating table {table}: {e}")

    conn.commit()
    conn.close()
    if not quiet:
        print("Onboarding migration completed successfully.")

if __name__ == "__main__":
    run_migration(quiet=False)
