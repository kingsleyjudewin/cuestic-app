from flask import Blueprint
from app.api.auth import auth_bp
from app.api.dashboard import dashboard_bp
from app.api.teams import teams_bp
from app.api.members import members_bp
from app.api.events import events_bp
from app.api.tasks import tasks_bp
from app.api.assignments import assignments_bp
from app.api.whatsapp import whatsapp_bp
from app.api.reminders import reminders_bp
from app.api.reports import reports_bp


def register_api_blueprints(app):
    """Register all API version 1 blueprints."""
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(teams_bp, url_prefix="/api/v1/teams")
    app.register_blueprint(members_bp, url_prefix="/api/v1/members")
    app.register_blueprint(events_bp, url_prefix="/api/v1/events")
    app.register_blueprint(tasks_bp, url_prefix="/api/v1")
    app.register_blueprint(assignments_bp, url_prefix="/api/v1/assignments")
    app.register_blueprint(whatsapp_bp, url_prefix="/api/v1")
    app.register_blueprint(reminders_bp, url_prefix="/api/v1")
    app.register_blueprint(reports_bp, url_prefix="/api/v1")
