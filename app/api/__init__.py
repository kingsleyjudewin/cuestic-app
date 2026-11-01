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
from app.api.notifications import notifications_bp
from app.api.users import users_bp
from app.api.me import me_bp
from app.api.documentation import documentation_bp
from app.api.media import media_bp
from app.api.communities import communities_bp
from app.api.mc import mc_bp
from app.api.research import research_bp


def register_api_blueprints(app):
    """Register all API version 1 blueprints."""
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(me_bp, url_prefix="/api/v1/me")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(teams_bp, url_prefix="/api/v1/teams")
    app.register_blueprint(members_bp, url_prefix="/api/v1/members")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(events_bp, url_prefix="/api/v1/events")
    app.register_blueprint(tasks_bp, url_prefix="/api/v1")
    app.register_blueprint(assignments_bp, url_prefix="/api/v1/assignments")
    app.register_blueprint(whatsapp_bp, url_prefix="/api/v1")
    app.register_blueprint(reminders_bp, url_prefix="/api/v1")
    app.register_blueprint(reports_bp, url_prefix="/api/v1")
    app.register_blueprint(notifications_bp, url_prefix="/api/v1/notifications")
    app.register_blueprint(documentation_bp, url_prefix="/api/v1/documentation")
    app.register_blueprint(media_bp, url_prefix="/api/v1/media")
    app.register_blueprint(communities_bp, url_prefix="/api/v1/communities")
    app.register_blueprint(mc_bp, url_prefix="/api/v1/mc")
    app.register_blueprint(research_bp, url_prefix="/api/v1/research")


