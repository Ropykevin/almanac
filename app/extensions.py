"""Shared Flask extensions.

Initialized here without an app, then bound in the application factory.
"""

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect


def client_ip() -> str:
    """Rate-limit key: prefer nginx X-Real-IP over spoofable X-Forwarded-For."""
    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    return get_remote_address()


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=client_ip, default_limits=[])

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access that page."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"
