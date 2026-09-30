"""Anti-abuse checks for public newsletter signup."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import urllib.error
import urllib.parse
import urllib.request

from flask import Request, current_app
from itsdangerous import BadSignature, URLSafeSerializer

from app.utils.client_info import looks_like_bot

logger = logging.getLogger(__name__)

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_FORM_SALT = "subscribe-form-started-v1"
_DEFAULT_MIN_FORM_SECONDS = 2.5
_DEFAULT_MAX_FORM_SECONDS = 60 * 60 * 6  # 6 hours

# Common disposable / throwaway providers used by signup bots.
_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.de",
        "sharklasers.com",
        "grr.la",
        "yopmail.com",
        "tempmail.com",
        "temp-mail.org",
        "temp-mail.io",
        "throwaway.email",
        "10minutemail.com",
        "10minutemail.net",
        "trashmail.com",
        "trashmail.me",
        "getnada.com",
        "maildrop.cc",
        "dispostable.com",
        "fakeinbox.com",
        "mailnesia.com",
        "moakt.com",
        "emailondeck.com",
        "mintemail.com",
        "mytemp.email",
        "tmpmail.org",
        "tmpmail.net",
        "discard.email",
        "mailcatch.com",
        "spamgourmet.com",
        "mailnull.com",
        "jetable.org",
        "nwldx.com",
        "getairmail.com",
        "mohmal.com",
        "tempail.com",
        "emailtemporanea.com",
        "crazymailing.com",
        "mailforspam.com",
        "spam4.me",
        "mail.tm",
        "inboxkitten.com",
        "guerrillamailblock.com",
        "pokemail.net",
        "spamfree24.org",
        "mailnesia.com",
    }
)

_RANDOM_LOCAL_RE = re.compile(r"^[a-z0-9]{18,}$", re.I)


@dataclass(frozen=True)
class SubscribeGuardResult:
    ok: bool
    reason: str | None = None
    # When True, pretend success so bots do not learn which check failed.
    silent: bool = False


def turnstile_enabled() -> bool:
    site = (current_app.config.get("TURNSTILE_SITE_KEY") or "").strip()
    secret = (current_app.config.get("TURNSTILE_SECRET_KEY") or "").strip()
    return bool(site and secret)


def honeypot_tripped(form) -> bool:
    """True when the hidden company/website field was filled (bot signal)."""
    value = getattr(form, "company", None)
    if value is None:
        return False
    data = (value.data or "").strip()
    return bool(data)


def bot_user_agent_blocked(request: Request) -> bool:
    ua = (request.user_agent.string if request.user_agent else "") or ""
    return looks_like_bot(ua)


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.secret_key, salt=_FORM_SALT)


def issue_form_started_token() -> str:
    return _serializer().dumps({"ts": time.time()})


def _timing_bounds() -> tuple[float, float]:
    min_s = current_app.config.get("SUBSCRIBE_FORM_MIN_SECONDS", _DEFAULT_MIN_FORM_SECONDS)
    max_s = current_app.config.get("SUBSCRIBE_FORM_MAX_SECONDS", _DEFAULT_MAX_FORM_SECONDS)
    try:
        min_seconds = float(min_s)
    except (TypeError, ValueError):
        min_seconds = _DEFAULT_MIN_FORM_SECONDS
    try:
        max_seconds = float(max_s)
    except (TypeError, ValueError):
        max_seconds = _DEFAULT_MAX_FORM_SECONDS
    return max(min_seconds, 0.0), max(max_seconds, 60.0)


def form_timing_invalid(token: str | None) -> str | None:
    """Return a reason code if the form was submitted too fast / expired / forged."""
    if not token:
        return "form_timing"
    try:
        payload = _serializer().loads(token)
        started = float(payload["ts"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return "form_timing"
    age = time.time() - started
    min_seconds, max_seconds = _timing_bounds()
    if age < min_seconds:
        return "form_too_fast"
    if age > max_seconds:
        return "form_expired"
    return None


def disposable_email(email: str | None) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if domain in _DISPOSABLE_DOMAINS:
        return True
    # Block common disposable subdomains: mail.temp-mail.org etc.
    parts = domain.split(".")
    if len(parts) >= 3:
        parent = ".".join(parts[-2:])
        if parent in _DISPOSABLE_DOMAINS:
            return True
    return False


def suspicious_email_local(email: str | None) -> bool:
    """Heuristic for long random local-parts common in bot dumps."""
    if not email or "@" not in email:
        return False
    local = email.rsplit("@", 1)[0].strip()
    return bool(_RANDOM_LOCAL_RE.match(local))


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    secret = (current_app.config.get("TURNSTILE_SECRET_KEY") or "").strip()
    if not secret:
        return True
    token = (token or "").strip()
    if not token:
        return False
    payload = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        _TURNSTILE_VERIFY_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json

            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("Turnstile verification request failed: %s", exc)
        return False
    return bool(body.get("success"))


def evaluate_subscribe_request(form, request: Request) -> SubscribeGuardResult:
    """Run honeypot / timing / email / UA / Turnstile checks for a subscribe POST."""
    if honeypot_tripped(form):
        logger.info("Subscribe blocked: honeypot tripped from %s", request.remote_addr)
        return SubscribeGuardResult(ok=False, reason="honeypot", silent=True)

    timing = form_timing_invalid(getattr(getattr(form, "form_started", None), "data", None))
    if timing == "form_too_fast":
        logger.info("Subscribe blocked: form too fast from %s", request.remote_addr)
        return SubscribeGuardResult(ok=False, reason=timing, silent=True)
    if timing in {"form_timing", "form_expired"}:
        logger.info("Subscribe blocked: %s from %s", timing, request.remote_addr)
        return SubscribeGuardResult(ok=False, reason=timing, silent=False)

    email = (getattr(getattr(form, "email", None), "data", None) or "").strip().lower()
    if disposable_email(email):
        logger.info("Subscribe blocked: disposable email %s", email)
        return SubscribeGuardResult(ok=False, reason="disposable_email", silent=True)

    if suspicious_email_local(email):
        logger.info("Subscribe blocked: suspicious local-part %s", email)
        return SubscribeGuardResult(ok=False, reason="suspicious_email", silent=True)

    if bot_user_agent_blocked(request):
        logger.info(
            "Subscribe blocked: bot UA from %s (%s)",
            request.remote_addr,
            (request.user_agent.string if request.user_agent else "")[:120],
        )
        return SubscribeGuardResult(ok=False, reason="bot_ua", silent=True)

    if turnstile_enabled():
        token = request.form.get("cf-turnstile-response")
        from app.utils.client_info import client_ip

        ip = client_ip(request)
        if not verify_turnstile(token, ip):
            logger.info("Subscribe blocked: Turnstile failed from %s", request.remote_addr)
            return SubscribeGuardResult(
                ok=False,
                reason="turnstile",
                silent=False,
            )

    return SubscribeGuardResult(ok=True)
