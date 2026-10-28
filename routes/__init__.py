from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.schools import schools_bp
from routes.students import students_bp
from routes.enrolment import enrolment_bp
from routes.single_id import single_id_bp
from routes.bulk_import import bulk_import_bp
from routes.bulk_generate import bulk_generate_bp
from routes.templates import templates_bp
from routes.print_queue import print_queue_bp
from routes.verification import verification_bp
from routes.reports import reports_bp
from routes.system import system_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="")
    app.register_blueprint(schools_bp, url_prefix="/schools")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(enrolment_bp, url_prefix="")
    app.register_blueprint(single_id_bp, url_prefix="/single-id")
    app.register_blueprint(bulk_import_bp, url_prefix="/bulk-import")
    app.register_blueprint(bulk_generate_bp, url_prefix="/bulk-generate")
    app.register_blueprint(templates_bp, url_prefix="/templates-designer")
    app.register_blueprint(print_queue_bp, url_prefix="/print-queue")
    app.register_blueprint(verification_bp, url_prefix="")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(system_bp, url_prefix="/system")
