import os
from flask import Flask, send_from_directory, abort
from flask_login import current_user
from sqlalchemy import inspect, text
from config import Config
from extensions import db, login_manager
from routes import register_blueprints
from models import School, User

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register all Blueprints
    register_blueprints(app)

    # Media File Serving Route for persistent photos, logos, cards, etc.
    @app.route("/media/<folder>/<filename>")
    def serve_media(folder, filename):
        valid_folders = {
            "photos": Config.PHOTOS_DIR,
            "logos": Config.LOGOS_DIR,
            "signatures": Config.SIGNATURES_DIR,
            "generated_cards": Config.GENERATED_CARDS_DIR,
            "pdfs": Config.PDFS_DIR
        }
        if folder not in valid_folders:
            abort(404)
        target_dir = valid_folders[folder]
        return send_from_directory(str(target_dir), filename)

    # Global context processor for active school and school switcher
    @app.context_processor
    def inject_school_context():
        from utils import get_current_school
        if current_user and current_user.is_authenticated:
            try:
                school = get_current_school()
                all_schools = School.query.filter_by(is_active=True).all()
                return dict(current_school=school, all_schools=all_schools)
            except Exception:
                return dict(current_school=None, all_schools=[])
        return dict(current_school=None, all_schools=[])

    # Register WhatsApp helpers for templates
    from utils import (
        clean_kenyan_phone_for_whatsapp,
        build_whatsapp_link,
        get_whatsapp_onboarding_share_url,
        get_whatsapp_parent_card_notice_url
    )
    app.jinja_env.filters["whatsapp_phone"] = clean_kenyan_phone_for_whatsapp
    app.jinja_env.filters["whatsapp_link"] = build_whatsapp_link
    app.jinja_env.globals["build_whatsapp_link"] = build_whatsapp_link
    app.jinja_env.globals["clean_whatsapp_phone"] = clean_kenyan_phone_for_whatsapp
    app.jinja_env.globals["get_whatsapp_onboarding_share_url"] = get_whatsapp_onboarding_share_url
    app.jinja_env.globals["get_whatsapp_parent_card_notice_url"] = get_whatsapp_parent_card_notice_url

    # Ensure database tables exist and migrations are applied
    # Skip in the reloader parent process so startup does not run heavy DB queries twice
    is_reloader_parent = app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    if not is_reloader_parent:
        with app.app_context():
            db.create_all()
            try:
                required_columns = {
                    "schools": {"onboarding_base_url": "VARCHAR(255)"},
                    "self_enrolments": {
                        "card_qr_token": "VARCHAR(64)",
                        "resubmission_count": "INTEGER NOT NULL DEFAULT 0"
                    },
                    "students": {"pending_card_qr_token": "VARCHAR(64)"}
                }
                with db.engine.begin() as connection:
                    for table, columns in required_columns.items():
                        existing = {column["name"] for column in inspect(db.engine).get_columns(table)}
                        for column_name, column_type in columns.items():
                            if column_name not in existing:
                                connection.execute(text(
                                    f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"
                                ))
            except Exception as e:
                app.logger.warning(f"Onboarding schema migration notice: {e}")
            try:
                from migrate_onboarding import run_migration
                run_migration(quiet=True)
            except Exception as e:
                app.logger.warning(f"Migration notice: {e}")

            # Seed initial default school if database is empty
            if School.query.count() == 0:
                default_school = School(
                    name="Alliance High School",
                    code="AHS-001",
                    motto="Strong to Serve",
                    po_box="P.O. Box 7 - 00902",
                    town="Kikuyu",
                    county="Kiambu",
                    phone="+254 722 000111",
                    email="info@alliancehigh.ac.ke",
                    website="https://alliancehigh.ac.ke",
                    primary_color="#1E3A8A",   # Royal Navy Blue
                    secondary_color="#F59E0B", # Gold
                    accent_color="#10B981",    # Emerald
                    card_bg_color="#FFFFFF",
                    text_color="#0F172A",
                    principal_name="Chief Principal",
                    academic_year="2026",
                    card_prefix="AHS-",
                    validity_years=4
                )
                db.session.add(default_school)
                db.session.commit()

            # Seed initial admin if empty
            if User.query.count() == 0:
                first_school = School.query.first()
                admin = User(
                    username="admin",
                    email="admin@schoolidsystem.ke",
                    full_name="System Administrator",
                    role="superadmin",
                    school_id=first_school.id if first_school else None,
                    is_active=True
                )
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    cert_file = os.environ.get("APP_TLS_CERT")
    key_file = os.environ.get("APP_TLS_KEY")
    if bool(cert_file) != bool(key_file):
        raise RuntimeError("Set both APP_TLS_CERT and APP_TLS_KEY to enable HTTPS.")
    if cert_file and (not os.path.isfile(cert_file) or not os.path.isfile(key_file)):
        raise RuntimeError("APP_TLS_CERT and APP_TLS_KEY must point to existing certificate and key files.")
    tls_context = (cert_file, key_file) if cert_file and key_file else None
    protocol = "https" if tls_context else "http"
    # Quick launch: enable debug without the heavy multi-second directory reloader by default
    debug_env = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true")
    print("=" * 65)
    print("  EduID Kenya — School ID Card Generation System")
    print(f"  Server URL: {protocol}://127.0.0.1:{port}")
    if tls_context:
        print("  HTTPS enabled; use a certificate trusted by each device and valid for its URL host.")
    print("  Ready for ID generation, student onboarding & printing")
    print("=" * 65)
    app.run(host="0.0.0.0", port=port, debug=debug_env, use_reloader=debug_env, ssl_context=tls_context)
