import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-replace-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'department_club.db')}")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    _is_postgres = "postgresql" in DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = (
        {
            "pool_size": 20,
            "max_overflow": 20,
            "pool_recycle": 300,
            "pool_timeout": 15,
            "pool_pre_ping": False,
            "connect_args": {
                "connect_timeout": 10,
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
    
    # Reminders
    CONFIRMATION_REMINDER_HOURS = int(os.environ.get("CONFIRMATION_REMINDER_HOURS", "24"))
    DEADLINE_REMINDER_HOURS = int(os.environ.get("DEADLINE_REMINDER_HOURS", "24"))
    ENABLE_BACKGROUND_SCHEDULER = os.environ.get("ENABLE_BACKGROUND_SCHEDULER", "false").lower() == "true"
    
    # CORS
    cors_env = os.environ.get("CORS_ORIGINS", "*")
    if cors_env.strip() == "*":
        CORS_ORIGINS = "*"
    else:
        CORS_ORIGINS = [
            origin.strip()
            for origin in cors_env.split(",")
            if origin.strip()
        ]
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "100000 per day;10000 per hour"
    RATELIMIT_STORAGE_URI = "memory://"
    
    # Swagger
    SWAGGER = {
        "title": "Department Club Task Assignment API",
        "uiversion": 3,
        "openapi": "3.0.2",
        "description": "Backend REST API for University Departmental Club Task Assignment",
        "version": "1.0.0",
        "specs_route": "/api/v1/docs/",
    }


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
    
    @classmethod
    def init_app(cls, app):
        if cls.SECRET_KEY == "dev-insecure-key-replace-in-production":
            raise ValueError("SECRET_KEY must be configured securely for production.")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
