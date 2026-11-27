import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

_INSECURE_DEFAULT_SECRET = "dev-insecure-key-replace-in-production"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _parse_origins(raw: str):
    if raw.strip() == "*":
        return "*"
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", _INSECURE_DEFAULT_SECRET)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'department_club.db')}")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    _is_postgres = "postgresql" in DATABASE_URL
    # Pool sized for one Gunicorn worker with GUNICORN_THREADS threads plus the scheduler thread.
    # Neon's pooled endpoint (-pooler host) multiplexes these onto server connections.
    # pre_ping is on because Neon closes idle connections when the compute scales to zero.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {
            "pool_size": _env_int("DB_POOL_SIZE", 10),
            "max_overflow": _env_int("DB_MAX_OVERFLOW", 10),
            "pool_recycle": _env_int("DB_POOL_RECYCLE", 300),
            "pool_timeout": _env_int("DB_POOL_TIMEOUT", 15),
            "pool_pre_ping": _env_bool("DB_POOL_PRE_PING", True),
            "connect_args": {
                "connect_timeout": _env_int("DB_CONNECT_TIMEOUT", 10),
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
        }
        if _is_postgres
        else {
            "pool_pre_ping": True,
        }
    )

    # Timezone & Localization
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
    DEFAULT_COUNTRY_CODE = os.environ.get("DEFAULT_COUNTRY_CODE", "+91")

    # Auth & Tokens
    TOKEN_EXPIRY_DAYS = int(os.environ.get("TOKEN_EXPIRY_DAYS", "30"))
    # Re-check revocation / account status against the database on every request (one indexed
    # lookup). Keeps logout and deactivation effective immediately in every server process.
    AUTH_CACHE_REVALIDATE = _env_bool("AUTH_CACHE_REVALIDATE", True)

    # Uploads: reject request bodies larger than this before they reach a view (bytes).
    MAX_CONTENT_LENGTH = _env_int("MAX_UPLOAD_MB", 30) * 1024 * 1024

    # Reminders
    CONFIRMATION_REMINDER_HOURS = int(os.environ.get("CONFIRMATION_REMINDER_HOURS", "24"))
    DEADLINE_REMINDER_HOURS = int(os.environ.get("DEADLINE_REMINDER_HOURS", "24"))
    ENABLE_BACKGROUND_SCHEDULER = _env_bool("ENABLE_BACKGROUND_SCHEDULER", False)
    REMINDER_SCAN_INTERVAL_MINUTES = _env_int("REMINDER_SCAN_INTERVAL_MINUTES", 15)

    # Heavy CPU/IO jobs (OCR, DOCX/AI report generation) allowed to run at the same time.
    # Extra requests wait up to HEAVY_JOB_QUEUE_TIMEOUT seconds, then get HTTP 503 "busy, retry".
    MAX_CONCURRENT_HEAVY_JOBS = _env_int("MAX_CONCURRENT_HEAVY_JOBS", 2)
    HEAVY_JOB_QUEUE_TIMEOUT = _env_int("HEAVY_JOB_QUEUE_TIMEOUT", 60)
    # Attendance OCR needs ~630 MB at peak; set ENABLE_OCR=false on 512 MB hosts (Render free).
    ENABLE_OCR = _env_bool("ENABLE_OCR", True)

    # Persistent file storage. Firebase Storage is used when configured; otherwise files go under
    # STORAGE_LOCAL_ROOT (use a Render persistent disk path in production, e.g. /var/data/storage).
    # (Read directly by app/services/firebase_storage_service.py.) Generated DOCX/charts under
    # instance/ are regenerable caches and are rebuilt on demand, so ephemeral disk is fine for them.
    STORAGE_LOCAL_ROOT = os.environ.get("STORAGE_LOCAL_ROOT") or os.path.join(BASE_DIR, "instance", "storage")

    # CORS: comma-separated explicit origins (e.g. https://cuestic.vercel.app). "*" allows any.
    CORS_ORIGINS = _parse_origins(os.environ.get("CORS_ORIGINS", "*"))
    # Optional regex for preview deployments, e.g. ^https://cuestic-[a-z0-9-]+\.vercel\.app$
    CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", "").strip() or None

    # Visitor (demo) accounts: comma-separated usernames that explore the admin UI on an empty,
    # read-only workspace. See app/utils/visitor_mode.py. Create one with `flask create-visitor`.
    VISITOR_USERNAMES = os.environ.get("VISITOR_USERNAMES", "visitor")

    # Security headers / HTTPS
    ENABLE_HSTS = False
    TRUST_PROXY_HEADERS = _env_bool("TRUST_PROXY_HEADERS", False)

    # Rate Limiting (per process; use a redis:// URI here if you run several instances)
    RATELIMIT_DEFAULT = "100000 per day;10000 per hour"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Swagger
    ENABLE_API_DOCS = _env_bool("ENABLE_API_DOCS", True)
    SWAGGER = {
        "title": "Department Club Task Assignment API",
        "uiversion": 3,
        "openapi": "3.0.2",
        "description": "Backend REST API for University Departmental Club Task Assignment",
        "version": "1.0.0",
        "specs_route": "/api/v1/docs/",
    }

    @classmethod
    def init_app(cls, app):
        """Hook for config-specific validation; called by create_app()."""


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = "development"
    RATELIMIT_ENABLED = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ENABLE_BACKGROUND_SCHEDULER = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    FLASK_ENV = "production"
    ENABLE_HSTS = _env_bool("ENABLE_HSTS", True)
    # Render terminates TLS and forwards X-Forwarded-For / X-Forwarded-Proto.
    TRUST_PROXY_HEADERS = _env_bool("TRUST_PROXY_HEADERS", True)
    # In production, never accept wildcard CORS silently: an unset value means "no browser origins".
    CORS_ORIGINS = _parse_origins(os.environ.get("CORS_ORIGINS", ""))

    @classmethod
    def init_app(cls, app):
        if not cls.SECRET_KEY or cls.SECRET_KEY == _INSECURE_DEFAULT_SECRET or len(cls.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production.")
        if cls.DATABASE_URL.startswith("sqlite"):
            raise ValueError("DATABASE_URL must point to PostgreSQL (Neon) in production, not SQLite.")
        if cls.CORS_ORIGINS == "*":
            app.logger.warning("CORS_ORIGINS='*' in production: any website may call this API from a browser.")
        elif not cls.CORS_ORIGINS and not cls.CORS_ORIGIN_REGEX:
            app.logger.warning("CORS_ORIGINS is empty: the Flutter web app will be blocked until it is set.")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
