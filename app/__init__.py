import os
from flask import Flask, jsonify
from app.config import config_by_name
from app.extensions import db, migrate, cors, limiter, swagger
from app.utils.errors import register_error_handlers
from app.api import register_api_blueprints


def create_app(config_name: str = None) -> Flask:
    """Application factory for the Department Club Task Assignment Backend."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    config_cls = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_cls)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configure CORS securely - never wildcard with credentials
    cors.init_app(
        app,
        origins=app.config.get("CORS_ORIGINS", ["http://localhost:3000"]),
        supports_credentials=False
    )
    
    # Configure rate limiter (disabled in testing)
    if not app.config.get("TESTING"):
        limiter.init_app(app)

    # Configure Flasgger Swagger UI
    swagger.init_app(app)

    # Register error handlers
    register_error_handlers(app)

    # Register API blueprints
    register_api_blueprints(app)

    # Root & Health Check routes
    @app.route("/", methods=["GET"])
    def root():
        return jsonify({
            "service": "Department Club Task Assignment API",
            "version": "1.0.0",
            "docs": "/api/v1/docs/",
            "health": "/health",
        }), 200

    @app.route("/health", methods=["GET"])
    def health_check():
        # Test database connection
        db_ok = True
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:
            db_ok = False

        status = "healthy" if db_ok else "unhealthy"
        return jsonify({
            "status": status,
            "database": "connected" if db_ok else "disconnected",
        }), 200 if db_ok else 503

    # Optional background scheduler
    if app.config.get("ENABLE_BACKGROUND_SCHEDULER") and not app.config.get("TESTING"):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from app.services.reminder_service import ReminderService

            scheduler = BackgroundScheduler()
            scheduler.add_job(
                func=lambda: _run_scheduler_job(app),
                trigger="interval",
                minutes=15,
                id="reminder_scan_job",
                replace_existing=True,
            )
            scheduler.start()
            app.logger.info("Background reminder scheduler started.")
        except Exception as e:
            app.logger.error("Failed to start background scheduler: %s", e)

    return app


def _run_scheduler_job(app):
    """Run scheduled reminder scan inside application context."""
    with app.app_context():
        try:
            from app.services.reminder_service import ReminderService
            ReminderService.scan_and_generate_reminders()
        except Exception as e:
            app.logger.error("Error executing scheduled reminder scan: %s", e)
