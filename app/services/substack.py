"""Fetch recent posts from a Substack publication feed."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubstackPost:
    title: str
    url: str
    published_label: str | None = None


def _feed_url(publication_url: str) -> str:
    base = publication_url.rstrip("/")
    if base.endswith("/feed"):
        return base
    if base.endswith("/archive"):
        base = base[: -len("/archive")]
    return f"{base}/feed"


def fetch_recent_posts(publication_url: str, *, limit: int = 12) -> list[SubstackPost]:
    """Return recent Substack posts from the public RSS feed, or [] on failure."""
    url = (publication_url or "").strip()
    if not url:
        return []

    feed = _feed_url(url)
    try:
        request = Request(
            feed,
            headers={"User-Agent": "AfricaAIAlmanac/1.0 (+https://almanac.africa)"},
        )
        with urlopen(request, timeout=8) as response:
            raw = response.read()
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("Substack feed fetch failed (%s): %s", feed, exc)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        logger.warning("Substack feed parse failed (%s): %s", feed, exc)
        return []

    posts: list[SubstackPost] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        published_label = None
        pub_date = (item.findtext("pubDate") or "").strip()
        if pub_date:
            try:
                published_label = parsedate_to_datetime(pub_date).strftime("%B %d, %Y")
            except (TypeError, ValueError, IndexError, OverflowError):
                published_label = pub_date
        posts.append(SubstackPost(title=title, url=link, published_label=published_label))
        if len(posts) >= limit:
            break
    return posts
