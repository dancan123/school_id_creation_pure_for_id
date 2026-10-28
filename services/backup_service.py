import os
import shutil
import zipfile
import datetime
from pathlib import Path
from config import Config

class BackupService:
    @staticmethod
    def create_full_backup():
        """Creates a timestamped zip backup of SQLite database and all photo/logo assets."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"school_id_backup_{timestamp}.zip"
        backup_path = Config.BACKUPS_DIR / backup_filename

        db_path = Config.STORAGE_DIR / "school_id_system.db"

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add DB if exists
            if db_path.exists():
                zf.write(db_path, arcname="school_id_system.db")

            # Add photos
            for folder_name in ["photos", "logos", "signatures"]:
                folder_dir = Config.STORAGE_DIR / folder_name
                if folder_dir.exists():
                    for f in folder_dir.glob("*"):
                        if f.is_file():
                            zf.write(f, arcname=f"{folder_name}/{f.name}")

        return backup_filename, backup_path

    @staticmethod
    def restore_backup(zip_path):
        """Restores DB and media assets from a zip backup."""
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(Config.STORAGE_DIR)
        return True
