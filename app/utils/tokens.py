"""Timed tokens for password reset and subscriptions."""

from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=current_app.config["SECRET_KEY"],
        salt=salt,
    )


def generate_reset_token(email: str) -> str:
    return _serializer("liminal-password-reset").dumps(email)


def verify_reset_token(token: str, max_age: int | None = None) -> str | None:
    """Return email if token is valid, otherwise None."""
    if max_age is None:
        max_age = current_app.config.get("PASSWORD_RESET_MAX_AGE", 3600)
    try:
        return _serializer("liminal-password-reset").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def generate_unsubscribe_token(email: str, publication_id: str) -> str:
    return _serializer("liminal-unsubscribe").dumps(
        {"email": email, "publication_id": publication_id}
    )


def verify_unsubscribe_token(token: str, max_age: int | None = None) -> dict | None:
    """Return payload dict or None. max_age default ~1 year for list-unsubscribe links."""
    if max_age is None:
        max_age = current_app.config.get("UNSUBSCRIBE_TOKEN_MAX_AGE", 60 * 60 * 24 * 365)
    try:
        payload = _serializer("liminal-unsubscribe").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    if "email" not in payload or "publication_id" not in payload:
        return None
    return payload


def _tracking_max_age() -> int:
    return int(current_app.config.get("NEWSLETTER_TRACKING_MAX_AGE", 60 * 60 * 24 * 90))


def generate_open_token(delivery_id: str) -> str:
    return _serializer("liminal-newsletter-open").dumps({"d": delivery_id})


def verify_open_token(token: str, max_age: int | None = None) -> str | None:
    """Return delivery id string or None."""
    if max_age is None:
        max_age = _tracking_max_age()
    try:
        payload = _serializer("liminal-newsletter-open").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict) or "d" not in payload:
        return None
    return str(payload["d"])


def generate_click_token(delivery_id: str, url: str) -> str:
    return _serializer("liminal-newsletter-click").dumps({"d": delivery_id, "u": url})


def verify_click_token(token: str, max_age: int | None = None) -> dict | None:
    """Return {delivery_id, url} or None."""
    if max_age is None:
        max_age = _tracking_max_age()
    try:
        payload = _serializer("liminal-newsletter-click").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    if "d" not in payload or "u" not in payload:
        return None
    return {"delivery_id": str(payload["d"]), "url": str(payload["u"])}
