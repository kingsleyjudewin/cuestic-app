import os
from flask import Flask, jsonify, request
from app.config import config_by_name
from app.extensions import db, migrate, cors, limiter, swagger
from app.utils.errors import register_error_handlers
from app.api import register_api_blueprints
from app.cli import register_cli_commands


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
    
    # Configure CORS securely - support development, Flutter Web, and configurable origins
    cors_origins = app.config.get("CORS_ORIGINS", "*")
    if app.config.get("DEBUG") or app.config.get("FLASK_ENV") == "development":
        if isinstance(cors_origins, list) and "*" not in cors_origins:
            cors_origins = list(cors_origins) + [
                r"^https?://localhost(:\d+)?$",
                r"^https?://127\.0\.0\.1(:\d+)?$",
                r"^https?://10\.\d+\.\d+\.\d+(:\d+)?$",
                r"^https?://192\.168\.\d+\.\d+(:\d+)?$"
            ]
        elif cors_origins == "*":
            cors_origins = "*"

    cors.init_app(
        app,
        resources={r"/*": {"origins": cors_origins}},
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin"],
        methods=["GET", "HEAD", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"]
    )
    
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            origin = request.headers.get("Origin") or "*"
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, OPTIONS, PUT, PATCH, DELETE"
            if request.headers.get("Access-Control-Request-Private-Network") == "true":
                response.headers["Access-Control-Allow-Private-Network"] = "true"
            return response

    @app.after_request
    def handle_pna_and_cors(response):
        origin = request.headers.get("Origin") or "*"
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, OPTIONS, PUT, PATCH, DELETE"
        if request.headers.get("Access-Control-Request-Private-Network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response
    
    # Configure rate limiter (disabled in testing or when RATELIMIT_ENABLED is False)
    if not app.config.get("TESTING") and app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)

    # Configure Flasgger Swagger UI
    swagger.init_app(app)

    # Register error handlers
    register_error_handlers(app)

    # Register API blueprints
    register_api_blueprints(app)

    # Register CLI commands
    register_cli_commands(app)

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
