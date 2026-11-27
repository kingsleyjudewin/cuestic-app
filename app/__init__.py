import os
import re
import sys
from flask import Flask, jsonify, request, redirect
from app.config import config_by_name
from app.extensions import db, migrate, limiter, swagger
from app.utils.errors import register_error_handlers
from app.api import register_api_blueprints
from app.cli import register_cli_commands

# Origins that are always allowed while developing locally (never in production).
_DEV_ORIGIN_PATTERNS = [
    re.compile(r"^https?://localhost(:\d+)?$"),
    re.compile(r"^https?://127\.0\.0\.1(:\d+)?$"),
    re.compile(r"^https?://10\.\d+\.\d+\.\d+(:\d+)?$"),
    re.compile(r"^https?://192\.168\.\d+\.\d+(:\d+)?$"),
]
_CORS_ALLOW_HEADERS = "Content-Type, Authorization, Accept, X-Requested-With, Origin"
_CORS_ALLOW_METHODS = "GET, HEAD, POST, OPTIONS, PUT, PATCH, DELETE"


def _build_origin_checker(app: Flask):
    """Return a function deciding whether a browser Origin may call this API."""
    origins = app.config.get("CORS_ORIGINS", "*")
    regex_src = app.config.get("CORS_ORIGIN_REGEX")
    origin_regex = re.compile(regex_src) if regex_src else None
    allow_dev = bool(app.config.get("DEBUG")) or app.config.get("FLASK_ENV") == "development"
    allowed_set = set(origins) if isinstance(origins, (list, tuple, set)) else set()

    def is_allowed(origin: str) -> bool:
        if not origin:
            return False
        if origins == "*":
            return True
        if origin.rstrip("/") in allowed_set:
            return True
        if origin_regex is not None and origin_regex.fullmatch(origin):
            return True
        if allow_dev and any(p.match(origin) for p in _DEV_ORIGIN_PATTERNS):
            return True
        return False

    return is_allowed


def _register_cors_and_security(app: Flask):
    is_allowed = _build_origin_checker(app)
    wildcard = app.config.get("CORS_ORIGINS", "*") == "*"
    allow_dev = bool(app.config.get("DEBUG")) or app.config.get("FLASK_ENV") == "development"

    def apply_cors(response):
        origin = request.headers.get("Origin")
        if origin and is_allowed(origin):
            # Bearer-token API (no cookies), so credentials are never allowed.
            response.headers["Access-Control-Allow-Origin"] = "*" if wildcard else origin
            response.headers["Access-Control-Allow-Headers"] = _CORS_ALLOW_HEADERS
            response.headers["Access-Control-Allow-Methods"] = _CORS_ALLOW_METHODS
            response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
            response.headers["Access-Control-Max-Age"] = "600"
            # Chrome Private Network Access: only needed for local development hosts.
            if allow_dev and request.headers.get("Access-Control-Request-Private-Network") == "true":
                response.headers["Access-Control-Allow-Private-Network"] = "true"
        if not wildcard:
            response.headers.add("Vary", "Origin")
        return response

    @app.before_request
    def handle_preflight_and_https():
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
        if app.config.get("ENABLE_HSTS") and forwarded_proto == "http" and request.path != "/health":
            # The proxy reports the client used plain HTTP: send it to HTTPS. Direct internal
            # requests (no proxy header, e.g. container health probes) are left alone.
            return redirect(request.url.replace("http://", "https://", 1), code=308)
        if request.method == "OPTIONS":
            return apply_cors(app.make_default_options_response())
        return None

    @app.after_request
    def add_cors_and_security_headers(response):
        if request.method != "OPTIONS":
            apply_cors(response)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if app.config.get("ENABLE_HSTS") and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def _configure_logging(app: Flask):
    """Send INFO+ application logs to stderr in production (Render captures stderr).

    Without this, Python's default WARNING level silently drops operational messages
    (scheduler runs, storage backend, migrations). Log lines never include tokens or passwords.
    """
    import logging
    if app.debug or app.testing:
        return
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if not any(getattr(h, "_cuestic", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        handler._cuestic = True
        root.addHandler(handler)
    root.setLevel(level)
    app.logger.setLevel(level)
    # Third-party libraries that are noisy at INFO.
    for noisy in ("alembic.runtime.plugins", "urllib3", "google", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _is_cli_invocation() -> bool:
    """True when running a `flask ...` CLI command (e.g. `flask db upgrade`), not a web server."""
    prog = os.path.basename(sys.argv[0]) if sys.argv else ""
    return prog in ("flask", "flask.exe") or (len(sys.argv) > 1 and sys.argv[1:2] == ["db"])


def create_app(config_name: str = None) -> Flask:
    """Application factory for the Department Club Task Assignment Backend."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    config_cls = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_cls)
    _configure_logging(app)
    config_cls.init_app(app)

    if app.config.get("TRUST_PROXY_HEADERS"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize extensions
    db.init_app(app)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migrations_dir = os.path.join(base_dir, "database", "migrations")
    migrate.init_app(app, db, directory=migrations_dir)

    _register_cors_and_security(app)

    # Configure rate limiter (disabled in testing or when RATELIMIT_ENABLED is False)
    if not app.config.get("TESTING") and app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)

    # Configure Flasgger Swagger UI
    if app.config.get("ENABLE_API_DOCS", True):
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
            "docs": "/api/v1/docs/" if app.config.get("ENABLE_API_DOCS", True) else None,
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
            db.session.rollback()

        status = "healthy" if db_ok else "unhealthy"
        return jsonify({
            "status": status,
            "database": "connected" if db_ok else "disconnected",
        }), 200 if db_ok else 503

    # Optional background scheduler. Safe with several processes: every scan takes a
    # database lock (see app/services/scheduler_service.py), so only one runs at a time.
    if (
        app.config.get("ENABLE_BACKGROUND_SCHEDULER")
        and not app.config.get("TESTING")
        and not _is_cli_invocation()
    ):
        from app.services.scheduler_service import start_background_scheduler
        start_background_scheduler(app)

    return app


def _run_scheduler_job(app):
    """Run scheduled reminder scan inside application context (kept for backward compatibility)."""
    from app.services.scheduler_service import run_reminder_scan
    return run_reminder_scan(app)
