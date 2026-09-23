"""Anti-abuse checks for public newsletter signup."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import urllib.error
import urllib.parse
import urllib.request

from flask import Request, current_app

from app.utils.client_info import looks_like_bot

logger = logging.getLogger(__name__)

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


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
    # Missing UA alone is too aggressive (privacy browsers); only known bot patterns.
    return looks_like_bot(ua)


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
    """Run honeypot / UA / Turnstile checks for a subscribe POST."""
    if honeypot_tripped(form):
        logger.info("Subscribe blocked: honeypot tripped from %s", request.remote_addr)
        return SubscribeGuardResult(ok=False, reason="honeypot", silent=True)

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
