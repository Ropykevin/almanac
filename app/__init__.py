"""Almanac Africa AI — application factory."""

from __future__ import annotations

import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError

from app.config import config_by_name
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.logging_config import configure_logging


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production'.
            Falls back to FLASK_ENV / FLASK_CONFIG, then 'development'.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG") or os.environ.get(
            "FLASK_ENV", "development"
        )

    config_class = config_by_name.get(config_name, config_by_name["default"])

    app = Flask(
        __name__,
        static_folder=config_class.STATIC_FOLDER,
        template_folder=config_class.TEMPLATE_FOLDER,
        instance_relative_config=True,
    )
    app.config.from_object(config_class)

    if hasattr(config_class, "init_app"):
        config_class.init_app(app)

    _register_extensions(app)
    configure_logging(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)
    _register_shell_context(app)

    from app.cli import register_cli

    register_cli(app)

    # Import models for Flask-Migrate metadata discovery.
    # Use "from app import models" (not "import app.models") so the local
    # Flask instance named `app` is not shadowed by the package module.
    from app import models  # noqa: F401

    app.logger.info(
        "Africa’s AI Almanac started (config=%s)",
        config_name,
    )
    return app


def _register_extensions(app: Flask) -> None:
    """Bind Flask extensions to the application."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_message = "Please log in to access that page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        import uuid

        from app.models import User

        if not user_id:
            return None
        try:
            return db.session.get(User, uuid.UUID(user_id))
        except (TypeError, ValueError):
            return None


def _register_blueprints(app: Flask) -> None:
    """Register application blueprints."""
    from app.blueprints.admin import admin_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)


def _register_error_handlers(app: Flask) -> None:
    """Register HTML error pages with logging."""

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def payload_too_large(error):
        app.logger.warning("Upload rejected: payload too large")
        return render_template("errors/413.html"), 413

    @app.errorhandler(429)
    def rate_limited(error):
        app.logger.warning("Rate limit exceeded: %s", getattr(error, "description", ""))
        return render_template("errors/429.html"), 429

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        app.logger.warning("CSRF failure: %s", error.description)
        return render_template("errors/400.html", csrf_failed=True), 400

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        try:
            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return render_template("errors/500.html"), 500


def _register_context_processors(app: Flask) -> None:
    """Inject site settings into all templates."""

    @app.context_processor
    def inject_site_settings():
        from app.services.site_settings import get_site_settings
        from app.utils.email import mail_status

        try:
            site = get_site_settings()
        except Exception:  # noqa: BLE001 — avoid breaking pages before migrations
            app.logger.debug("Site settings unavailable", exc_info=True)
            site = None
        try:
            mail = mail_status()
        except Exception:  # noqa: BLE001
            mail = {"configured": False, "server": "", "sender": "", "username": "", "port": "587"}
        return {"site": site, "mail": mail}


def _register_shell_context(app: Flask) -> None:
    """Expose common objects in `flask shell`."""

    @app.shell_context_processor
    def make_shell_context():
        from app import models
        from app.extensions import db as database

        return {"db": database, "models": models}
