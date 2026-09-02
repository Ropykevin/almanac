"""Email helpers — logs messages in development when SMTP is unset."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage

from flask import current_app, url_for

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


class MailNotConfiguredError(RuntimeError):
    """Raised when a real SMTP send is required but MAIL_SERVER is unset."""


_PLACEHOLDER_MAIL_HOSTS = {
    "smtp.yourprovider.com",
    "smtp.example.com",
    "localhost",
    "127.0.0.1",
}


def mail_is_configured() -> bool:
    """True when MAIL_SERVER is set so messages leave the app over SMTP."""
    server = (current_app.config.get("MAIL_SERVER") or "").strip().lower()
    if not server or server in _PLACEHOLDER_MAIL_HOSTS:
        return False
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
    # Login credentials are optional for open relays; if a username is set,
    # require a password so half-configured Zoho setups don't look "active".
    if username and not password:
        return False
    return True


def mail_status() -> dict[str, str | bool]:
    """Admin-facing snapshot of outbound mail config (no secrets)."""
    server = (current_app.config.get("MAIL_SERVER") or "").strip()
    sender = (current_app.config.get("MAIL_DEFAULT_SENDER") or "").strip()
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
    configured = mail_is_configured()
    placeholder = server.lower() in _PLACEHOLDER_MAIL_HOSTS
    return {
        "configured": configured,
        "server": server,
        "sender": sender or username,
        "username": username,
        "port": str(current_app.config.get("MAIL_PORT") or 587),
        "needs_password": bool(username and not password),
        "placeholder_server": placeholder,
    }


def html_to_plain(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    require_smtp: bool = False,
) -> None:
    mail_server = (current_app.config.get("MAIL_SERVER") or "").strip()
    if not mail_server:
        if require_smtp:
            raise MailNotConfiguredError(
                "SMTP is not configured. Set MAIL_SERVER (and usually "
                "MAIL_USERNAME / MAIL_PASSWORD / MAIL_DEFAULT_SENDER) in .env, "
                "then restart the app."
            )
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

    try:
        with smtplib.SMTP(mail_server, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP login failed. Check MAIL_USERNAME / MAIL_PASSWORD "
            "(use a Zoho app password, not your normal mailbox password)."
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise RuntimeError(f"Recipient refused by mail server: {to_email}") from exc
    except smtplib.SMTPSenderRefused as exc:
        raise RuntimeError(
            f"Sender refused by mail server: {message['From']}. "
            "From address must match the Zoho mailbox."
        ) from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP error: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not connect to {mail_server}:{port} — {exc}") from exc

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


def send_html_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    require_smtp: bool = True,
) -> None:
    """Send an HTML newsletter (plain-text fallback derived from HTML).

    Newsletter campaigns require SMTP by default so “sent” means delivered,
    not merely logged.
    """
    _send_email(
        to_email=to_email,
        subject=subject,
        body=html_to_plain(html_body) or subject,
        html_body=html_body,
        require_smtp=require_smtp,
    )
