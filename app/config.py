"""Application configuration classes for Almanac Africa AI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")
    APP_NAME = "Almanac Africa AI"

    # SQLAlchemy / PostgreSQL
    SQLALCHEMY_DATABASE_URI = _env(
        "DATABASE_URL",
        "postgresql+psycopg://liminal:liminal@localhost:5432/liminal_ai_africa",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Flask-WTF / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False  # set True behind HTTPS terminators if needed

    # Flask-Login / secure cookies
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14  # 14 days
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_NAME = "liminal_session"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days

    # Rate limiting (Flask-Limiter)
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = _env("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = None

    # Password reset tokens (seconds)
    PASSWORD_RESET_MAX_AGE = int(_env("PASSWORD_RESET_MAX_AGE", "3600"))
    # Unsubscribe link lifetime (default 365 days)
    UNSUBSCRIBE_TOKEN_MAX_AGE = int(
        _env("UNSUBSCRIBE_TOKEN_MAX_AGE", str(60 * 60 * 24 * 365))
    )
    # Open/click tracking token lifetime (default 90 days)
    NEWSLETTER_TRACKING_MAX_AGE = int(
        _env("NEWSLETTER_TRACKING_MAX_AGE", str(60 * 60 * 24 * 90))
    )

    # Optional SMTP — when unset, reset links are logged to the app logger
    MAIL_SERVER = _env("MAIL_SERVER")
    MAIL_PORT = int(_env("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env("MAIL_USE_TLS", "1") in {"1", "true", "True", "yes"}
    MAIL_USERNAME = _env("MAIL_USERNAME")
    MAIL_PASSWORD = _env("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = _env("MAIL_DEFAULT_SENDER", "noreply@almanac.local")

    # Paths
    STATIC_FOLDER = "static"
    TEMPLATE_FOLDER = "templates"
    UPLOAD_FOLDER = str(BASE_DIR / "app" / "static" / "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB uploads (docs / PDFs)

    # Logging
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    LOG_TO_STDOUT = _env("LOG_TO_STDOUT", "0") in {"1", "true", "True", "yes"}
    LOG_DIR = BASE_DIR / "logs"


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG = True
    TESTING = False
    LOG_LEVEL = _env("LOG_LEVEL", "DEBUG")
    LOG_TO_STDOUT = _env("LOG_TO_STDOUT", "1") in {"1", "true", "True", "yes"}
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Test suite settings."""

    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = _env("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}
    LOG_LEVEL = "WARNING"
    LOG_TO_STDOUT = True
    PASSWORD_RESET_MAX_AGE = 3600


def _build_database_url_from_parts() -> str | None:
    """Build SQLAlchemy URL from DB_HOST + POSTGRES_* (Docker Compose path)."""
    host = _env("DB_HOST")
    password = _env("POSTGRES_PASSWORD")
    if not host or not password:
        return None
    from urllib.parse import quote_plus

    user = quote_plus(_env("POSTGRES_USER", "almanac") or "almanac")
    password = quote_plus(password)
    port = _env("DB_PORT", "5432") or "5432"
    db = quote_plus(_env("POSTGRES_DB", "almanac_africa_ai") or "almanac_africa_ai")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def _normalize_database_url(db_uri: str) -> str:
    if db_uri.startswith("postgres://"):
        return "postgresql+psycopg://" + db_uri[len("postgres://") :]
    if db_uri.startswith("postgresql://") and "+psycopg" not in db_uri:
        return "postgresql+psycopg://" + db_uri[len("postgresql://") :]
    return db_uri


class ProductionConfig(Config):
    """Production settings — secrets must come from the environment."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True
    PREFERRED_URL_SCHEME = "https"
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    LOG_TO_STDOUT = _env("LOG_TO_STDOUT", "1") in {"1", "true", "True", "yes"}

    _WEAK_SECRETS = {
        None,
        "",
        "dev-only-change-me",
        "change-me-in-production",
        "change-me-to-a-long-random-string",
    }

    @classmethod
    def init_app(cls, app) -> None:
        secret = _env("SECRET_KEY")
        if secret in cls._WEAK_SECRETS:
            raise RuntimeError(
                "SECRET_KEY must be set to a strong random value in production."
            )
        app.config["SECRET_KEY"] = secret

        db_uri = _env("DATABASE_URL") or _build_database_url_from_parts()
        if not db_uri:
            raise RuntimeError(
                "DATABASE_URL must be set in production "
                "(or DB_HOST + POSTGRES_PASSWORD for Docker)."
            )
        app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(db_uri)

        # Trust X-Forwarded-* when behind a reverse proxy / load balancer.
        if _env("PROXY_FIX", "1") in {"1", "true", "True", "yes"}:
            from werkzeug.middleware.proxy_fix import ProxyFix

            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=1,
                x_proto=1,
                x_host=1,
                x_prefix=1,
            )

        scheme = _env("PREFERRED_URL_SCHEME", "https")
        if scheme:
            app.config["PREFERRED_URL_SCHEME"] = scheme

        sender = _env("MAIL_DEFAULT_SENDER")
        if sender:
            app.config["MAIL_DEFAULT_SENDER"] = sender


config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
