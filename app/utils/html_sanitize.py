"""Sanitize article HTML to a semantic allowlist."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "hr",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "sub",
    "sup",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "cite",
    "pre",
    "code",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "caption",
    "colgroup",
    "col",
    "figure",
    "figcaption",
    "img",
    "iframe",
    "video",
    "source",
    "aside",
    "section",
    "div",
    "span",
    "mark",
    "abbr",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "title", "lang", "dir", "role"],
    "a": ["href", "title", "rel", "target", "name"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "iframe": [
        "src",
        "width",
        "height",
        "allow",
        "allowfullscreen",
        "frameborder",
        "title",
        "loading",
        "referrerpolicy",
    ],
    "video": ["src", "controls", "width", "height", "poster", "preload"],
    "source": ["src", "type"],
    "td": ["colspan", "rowspan", "scope"],
    "th": ["colspan", "rowspan", "scope"],
    "col": ["span"],
    "ol": ["start", "type"],
    "abbr": ["title"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_IFRAME_HOSTS = {
    "www.youtube.com",
    "youtube.com",
    "www.youtube-nocookie.com",
    "youtube-nocookie.com",
    "player.vimeo.com",
}


def _iframe_src_allowed(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in _IFRAME_HOSTS


def sanitize_article_html(html: str | None) -> str | None:
    """Clean editor HTML; returns None for empty content."""
    if html is None:
        return None
    stripped = html.strip()
    if not stripped or stripped in {"<p></p>", "<p><br></p>", "<p><br/></p>"}:
        return None

    cleaned = bleach.clean(
        stripped,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )

    def _filter_iframe(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, flags=re.I)
        if not src_match or not _iframe_src_allowed(src_match.group(1)):
            return ""
        if "loading=" not in tag.lower():
            tag = tag.replace("<iframe", '<iframe loading="lazy"', 1)
        if "referrerpolicy=" not in tag.lower():
            tag = tag.replace(
                "<iframe",
                '<iframe referrerpolicy="strict-origin-when-cross-origin"',
                1,
            )
        return tag

    cleaned = re.sub(
        r"<iframe\b[^>]*>.*?</iframe>",
        _filter_iframe,
        cleaned,
        flags=re.I | re.S,
    )
    cleaned = re.sub(r"<iframe\b[^>]*/>", _filter_iframe, cleaned, flags=re.I)

    cleaned = re.sub(
        r'(<a\b[^>]*\btarget=["\']_blank["\'][^>]*)>',
        lambda m: (
            m.group(1)
            + (
                ' rel="noopener noreferrer">'
                if "rel=" not in m.group(1).lower()
                else ">"
            )
        ),
        cleaned,
        flags=re.I,
    )

    cleaned = cleaned.strip()
    return cleaned or None
