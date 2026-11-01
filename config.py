import os
import hashlib
from pathlib import Path

# Python 3.8 Windows OpenSSL compatibility patch for libraries like reportlab
_orig_md5 = hashlib.md5
def _safe_md5(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return _orig_md5(*args, **kwargs)
hashlib.md5 = _safe_md5

# Base workspace directory
BASE_DIR = Path(__file__).resolve().parent

# Persistent Storage Directory
# Can be configured via environment variable (e.g. for user APPDATA on Windows or /var/lib/school_id on Linux)
STORAGE_DIR = Path(os.environ.get("SCHOOL_ID_DATA_DIR", BASE_DIR / "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Subdirectories for data assets
PHOTOS_DIR = STORAGE_DIR / "photos"
LOGOS_DIR = STORAGE_DIR / "logos"
SIGNATURES_DIR = STORAGE_DIR / "signatures"
STAMPS_DIR = STORAGE_DIR / "stamps"
GENERATED_CARDS_DIR = STORAGE_DIR / "generated_cards"
PDFS_DIR = STORAGE_DIR / "pdfs"
UPLOADS_DIR = STORAGE_DIR / "uploads"
BACKUPS_DIR = STORAGE_DIR / "backups"

for folder in [PHOTOS_DIR, LOGOS_DIR, SIGNATURES_DIR, STAMPS_DIR, GENERATED_CARDS_DIR, PDFS_DIR, UPLOADS_DIR, BACKUPS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "kenya-school-id-production-secret-key-2026-secure")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    
    # Database: Default to persistent SQLite in STORAGE_DIR; support PostgreSQL via DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        f"sqlite:///{STORAGE_DIR / 'school_id_system.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload limits: 100MB (to allow ZIP archives with photos and large Excel files)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    
    # Card Printing Constants (CR80 standard)
    CR80_WIDTH_MM = 85.60
    CR80_HEIGHT_MM = 53.98
    DPI = 300  # High-resolution print quality
    
    # Directories
    STORAGE_DIR = STORAGE_DIR
    PHOTOS_DIR = PHOTOS_DIR
    LOGOS_DIR = LOGOS_DIR
    SIGNATURES_DIR = SIGNATURES_DIR
    STAMPS_DIR = STAMPS_DIR
    GENERATED_CARDS_DIR = GENERATED_CARDS_DIR
    PDFS_DIR = PDFS_DIR
    UPLOADS_DIR = UPLOADS_DIR
    BACKUPS_DIR = BACKUPS_DIR
    
    ALLOWED_EXTENSIONS_IMAGE = {"png", "jpg", "jpeg", "webp"}
    ALLOWED_EXTENSIONS_DATA = {"xlsx", "xls", "csv"}
    ALLOWED_EXTENSIONS_ARCHIVE = {"zip"}

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
