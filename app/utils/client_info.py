"""Lightweight client metadata for analytics (browser + country hints)."""

from __future__ import annotations

import re

from flask import Request

_COUNTRY_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "NG": "Nigeria",
    "KE": "Kenya",
    "ZA": "South Africa",
    "GH": "Ghana",
    "EG": "Egypt",
    "ET": "Ethiopia",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "RW": "Rwanda",
    "SN": "Senegal",
    "CI": "Côte d'Ivoire",
    "MA": "Morocco",
    "FR": "France",
    "DE": "Germany",
    "IN": "India",
    "BR": "Brazil",
    "AU": "Australia",
    "NL": "Netherlands",
    "AE": "United Arab Emirates",
    "XX": "Unknown",
    "T1": "Tor",
}


def parse_browser(user_agent: str | None) -> str:
    ua = user_agent or ""
    checks = [
        ("Edg/", "Edge"),
        ("OPR/", "Opera"),
        ("Opera", "Opera"),
        ("Chrome/", "Chrome"),
        ("CriOS/", "Chrome"),
        ("Firefox/", "Firefox"),
        ("FxiOS/", "Firefox"),
        ("Safari/", "Safari"),
        ("MSIE", "Internet Explorer"),
        ("Trident/", "Internet Explorer"),
        ("bot", "Bot"),
        ("spider", "Bot"),
        ("crawl", "Bot"),
    ]
    lower = ua.lower()
    for needle, label in checks:
        if needle.lower() in lower or needle in ua:
            if label == "Safari" and ("Chrome/" in ua or "CriOS/" in ua):
                continue
            return label
    if not ua.strip():
        return "Unknown"
    return "Other"


def country_from_request(request: Request) -> str:
    """Best-effort country from common CDN/proxy headers."""
    headers = request.headers
    raw = (
        headers.get("CF-IPCountry")
        or headers.get("CloudFront-Viewer-Country")
        or headers.get("X-AppEngine-Country")
        or headers.get("X-Country-Code")
        or headers.get("X-Geo-Country")
        or ""
    ).strip().upper()
    if not raw or raw in {"XX", "ZZ"}:
        # Local / private IPs
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[
            0
        ].strip()
        if ip.startswith(("127.", "10.", "192.168.", "172.")) or ip in {"::1", "localhost"}:
            return "Local"
        return "Unknown"
    return _COUNTRY_NAMES.get(raw, raw)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:100]
    if request.remote_addr:
        return request.remote_addr[:100]
    return None


_BOT_RE = re.compile(r"bot|spider|crawl|slurp|facebookexternalhit", re.I)


def looks_like_bot(user_agent: str | None) -> bool:
    return bool(user_agent and _BOT_RE.search(user_agent))
