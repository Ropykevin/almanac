"""SEO helpers: meta tags, Open Graph, Twitter Cards, JSON-LD."""

from __future__ import annotations

import re
from typing import Any

from flask import current_app, url_for

from app.models import Article
from app.utils.email import html_to_plain

DEFAULT_META_DESCRIPTION = (
    "Ideas, analysis, and insight on AI governance across Africa."
)


def site_name() -> str:
    try:
        from app.services.site_settings import get_site_settings

        return get_site_settings().name
    except Exception:  # noqa: BLE001
        return current_app.config.get("APP_NAME", "Africa’s AI Almanac")


def _site_settings_safe():
    try:
        from app.services.site_settings import get_site_settings

        return get_site_settings()
    except Exception:  # noqa: BLE001
        return None


def absolute_url(path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return url_for("static", filename=path_or_url.lstrip("/"), _external=True)


def truncate(text: str | None, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def site_default_image() -> str | None:
    """Fallback social image from site logo or banner."""
    site = _site_settings_safe()
    if site is None:
        return None
    for candidate in (site.banner_url, site.logo_url):
        if not candidate:
            continue
        if candidate.startswith(("http://", "https://")):
            return candidate
        # url_for("static") already used in site settings; may be relative
        if candidate.startswith("/"):
            return url_for("main.index", _external=True).rstrip("/") + candidate
        return absolute_url(candidate)
    return None


def article_description(article: Article) -> str:
    raw = (
        article.seo_description
        or article.excerpt
        or article.subtitle
        or html_to_plain(article.content or "")
        or article.title
    )
    return truncate(raw, 160)


def article_page_title(article: Article) -> str:
    base = (article.seo_title or article.title or "").strip()
    return f"{base} — {site_name()}"


def article_canonical(article: Article) -> str:
    if article.canonical_url and article.canonical_url.strip():
        return article.canonical_url.strip()
    return url_for("main.article_detail", slug=article.slug, _external=True)


def article_image_url(article: Article) -> str | None:
    if article.featured_image_media and article.featured_image_media.path:
        return url_for(
            "static",
            filename=article.featured_image_media.path,
            _external=True,
        )
    return None


def organization_json_ld() -> dict[str, Any]:
    site = _site_settings_safe()
    name = site.name if site else site_name()
    data: dict[str, Any] = {
        "@type": "Organization",
        "name": name,
        "url": url_for("main.index", _external=True),
    }
    if site and site.contact_email:
        data["email"] = site.contact_email
    logo = site.logo_url if site else None
    if logo:
        if logo.startswith(("http://", "https://")):
            data["logo"] = logo
        elif logo.startswith("/"):
            data["logo"] = url_for("main.index", _external=True).rstrip("/") + logo
        else:
            data["logo"] = absolute_url(logo)
    same_as = [link["url"] for link in (site.social_links if site else [])]
    if same_as:
        data["sameAs"] = same_as
    return data


def article_json_ld(article: Article) -> dict[str, Any]:
    publisher = organization_json_ld()
    publisher["@type"] = "Organization"
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": article.seo_title or article.title,
        "description": article_description(article),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": article_canonical(article),
        },
        "url": article_canonical(article),
        "isAccessibleForFree": True,
        "publisher": publisher,
    }
    if article.published_at:
        data["datePublished"] = article.published_at.isoformat()
    if article.updated_at:
        data["dateModified"] = article.updated_at.isoformat()
    if article.author:
        data["author"] = {
            "@type": "Person",
            "name": article.author.full_name,
        }
    image = article_image_url(article)
    if image:
        data["image"] = [image]
    if article.reading_time:
        data["timeRequired"] = f"PT{int(article.reading_time)}M"
    keywords = [c.name for c in (article.categories or [])] + [
        t.name for t in (article.tags or [])
    ]
    if keywords:
        data["keywords"] = ", ".join(keywords)
    return data


def article_seo_context(article: Article) -> dict[str, Any]:
    description = article_description(article)
    canonical = article_canonical(article)
    image = article_image_url(article) or site_default_image()
    title = article_page_title(article)
    return {
        "page_title": title,
        "meta_description": description,
        "canonical_url": canonical,
        "og_type": "article",
        "og_title": article.seo_title or article.title,
        "og_description": description,
        "og_url": canonical,
        "og_image": image,
        "og_site_name": site_name(),
        "twitter_card": "summary_large_image" if image else "summary",
        "twitter_title": article.seo_title or article.title,
        "twitter_description": description,
        "twitter_image": image,
        "json_ld": article_json_ld(article),
        "article_published_time": (
            article.published_at.isoformat() if article.published_at else None
        ),
        "article_modified_time": (
            article.updated_at.isoformat() if article.updated_at else None
        ),
        "article_author": article.author.full_name if article.author else None,
        "article_section": (
            article.categories[0].name if article.categories else None
        ),
        "article_tags": [t.name for t in (article.tags or [])],
    }


def default_seo_context(
    *,
    title: str | None = None,
    description: str | None = None,
    path_endpoint: str = "main.index",
    include_website_json_ld: bool = False,
    **endpoint_kwargs,
) -> dict[str, Any]:
    name = site_name()
    page_title = title or name
    if title and name not in title:
        page_title = f"{title} — {name}"
    site = _site_settings_safe()
    fallback_desc = (
        (site.description if site and site.description else None)
        or DEFAULT_META_DESCRIPTION
    )
    desc = truncate(description or fallback_desc)
    url = url_for(path_endpoint, _external=True, **endpoint_kwargs)
    image = site_default_image()
    json_ld: dict[str, Any] | None = None
    if include_website_json_ld:
        json_ld = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "name": name,
                    "url": url_for("main.index", _external=True),
                    "description": desc,
                    "publisher": {"@id": url_for("main.index", _external=True) + "#organization"},
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": (
                            url_for("main.search", _external=True)
                            + "?q={search_term_string}"
                        ),
                        "query-input": "required name=search_term_string",
                    },
                },
                {
                    **organization_json_ld(),
                    "@id": url_for("main.index", _external=True) + "#organization",
                },
            ],
        }
    return {
        "page_title": page_title,
        "meta_description": desc,
        "canonical_url": url,
        "og_type": "website",
        "og_title": title or name,
        "og_description": desc,
        "og_url": url,
        "og_image": image,
        "og_site_name": name,
        "twitter_card": "summary_large_image" if image else "summary",
        "twitter_title": title or name,
        "twitter_description": desc,
        "twitter_image": image,
        "json_ld": json_ld,
        "article_published_time": None,
        "article_modified_time": None,
        "article_author": None,
        "article_section": None,
        "article_tags": [],
    }
