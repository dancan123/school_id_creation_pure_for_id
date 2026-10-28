import sqlite3

db_path = "storage/school_id_system.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(students)")
existing = [row[1] for row in cur.fetchall()]
print("Existing students cols:", existing)

adds = [
    ("curriculum_type",      "TEXT NOT NULL DEFAULT 'CBC'"),
    ("enrolment_status",     "TEXT NOT NULL DEFAULT 'active'"),
    ("self_enrolment_token", "TEXT"),  # UNIQUE index added separately
]
for col, defn in adds:
    if col not in existing:
        cur.execute(f"ALTER TABLE students ADD COLUMN {col} {defn}")
        print(f"  Added: students.{col}")
    else:
        print(f"  Already exists: {col}")

conn.commit()
conn.close()
print("Migration complete.")
