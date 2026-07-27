"""Email helpers — logs messages in development when SMTP is unset."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage

from flask import current_app, url_for

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def html_to_plain(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    mail_server = current_app.config.get("MAIL_SERVER")
    if not mail_server:
        preview = html_body or body
        current_app.logger.info(
            "Email to %s (SMTP not configured — body logged):\nSubject: %s\n%s",
            to_email,
            subject,
            preview[:4000],
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@localhost")
    message["To"] = to_email
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    port = int(current_app.config.get("MAIL_PORT", 587))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    with smtplib.SMTP(mail_server, port, timeout=20) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)

    logger.info("Email sent to %s (%s)", to_email, subject)


def send_password_reset_email(to_email: str, token: str) -> None:
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    subject = f"Reset your {current_app.config['APP_NAME']} password"
    body = (
        f"Hello,\n\n"
        f"We received a request to reset your password.\n"
        f"Open this link to choose a new password (valid for "
        f"{current_app.config.get('PASSWORD_RESET_MAX_AGE', 3600) // 60} minutes):\n\n"
        f"{reset_url}\n\n"
        f"If you did not request this, you can ignore this email.\n"
    )
    _send_email(to_email=to_email, subject=subject, body=body)


def send_subscription_verification_email(to_email: str, token: str) -> None:
    verify_url = url_for("main.verify_subscription", token=token, _external=True)
    subject = f"Confirm your subscription to {current_app.config['APP_NAME']}"
    body = (
        f"Hello,\n\n"
        f"Please confirm your subscription to {current_app.config['APP_NAME']}:\n\n"
        f"{verify_url}\n\n"
        f"If you did not request this, you can ignore this email.\n"
    )
    _send_email(to_email=to_email, subject=subject, body=body)


def send_unsubscribe_confirmation_email(to_email: str) -> None:
    subject = f"You unsubscribed from {current_app.config['APP_NAME']}"
    body = (
        f"Hello,\n\n"
        f"You have been unsubscribed from {current_app.config['APP_NAME']}.\n"
        f"You can subscribe again any time from the website.\n"
    )
    _send_email(to_email=to_email, subject=subject, body=body)


def send_html_email(*, to_email: str, subject: str, html_body: str) -> None:
    """Send an HTML newsletter (plain-text fallback derived from HTML)."""
    _send_email(
        to_email=to_email,
        subject=subject,
        body=html_to_plain(html_body) or subject,
        html_body=html_body,
    )
