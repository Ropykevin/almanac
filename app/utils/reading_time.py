"""Reading time estimation."""

from __future__ import annotations

import re

WORDS_PER_MINUTE = 200
_TAG_RE = re.compile(r"<[^>]+>")


def estimate_reading_time(content: str | None) -> int:
    """Estimate minutes to read HTML/plain content (minimum 1 if non-empty)."""
    if not content or not content.strip():
        return 0
    text = _TAG_RE.sub(" ", content)
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0
    return max(1, round(len(words) / WORDS_PER_MINUTE))
