"""Publication site settings (branding, social, footer, contact, theme)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from flask import url_for
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Media, Publication, Setting
from app.services.media import MediaUploadError, save_image_upload
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity

SETTING_DEFAULTS: dict[str, str] = {
    "tagline": "Intelligence · Africa · Culture",
    "home_welcome": (
        "It’s a privilege to have you with us. As these rules begin to take shape "
        "across the continent, having your perspective in the room makes the work better. "
        "Thank you for helping us watch over Africa’s digital future—we’re glad you’re here."
    ),
    "footer_blurb": (
        "A premium journal of African AI — reporting at the intersection "
        "of technology, policy, and culture."
    ),
    "footer_copyright": "",
    "contact_email": "hello@almanac.africa",
    "contact_phone": "",
    "contact_address": "",
    "social_twitter": "",
    "social_linkedin": "",
    "social_facebook": "",
    "social_instagram": "",
    "social_youtube": "",
    "social_substack": "",
    "google_site_verification": "",
    "theme_primary_color": "#0f766e",
}

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass
class SiteSettings:
    publication_id: str
    name: str
    description: str
    tagline: str
    home_welcome: str
    footer_blurb: str
    footer_copyright: str
    contact_email: str
    contact_phone: str
    contact_address: str
    social_twitter: str
    social_linkedin: str
    social_facebook: str
    social_instagram: str
    social_youtube: str
    social_substack: str
    google_site_verification: str
    primary_color: str
    logo_url: str | None = None
    logo_id: str | None = None
    banner_url: str | None = None
    social_links: list[dict[str, str]] = field(default_factory=list)

    @property
    def copyright_line(self) -> str:
        if self.footer_copyright.strip():
            return self.footer_copyright.strip()
        return f"© {self.name}"

    @property
    def google_verification_token(self) -> str | None:
        """Search Console HTML-tag token from settings or GOOGLE_SITE_VERIFICATION."""
        from flask import current_app

        token = (self.google_site_verification or "").strip()
        if token:
            return token
        configured = (current_app.config.get("GOOGLE_SITE_VERIFICATION") or "").strip()
        return configured or None

    @property
    def substack_archive_url(self) -> str | None:
        from flask import current_app

        url = (self.social_substack or "").strip()
        if url:
            return url.rstrip("/")
        configured = (
            current_app.config.get("SUBSTACK_ARCHIVE_URL")
            or current_app.config.get("SUBSTACK_URL")
            or ""
        ).strip()
        return configured.rstrip("/") or None


class SettingsError(ValueError):
    """Invalid settings input."""


def _load_kv(publication_id) -> dict[str, str]:
    rows = db.session.scalars(
        select(Setting).where(Setting.publication_id == publication_id)
    ).all()
    values = dict(SETTING_DEFAULTS)
    for row in rows:
        if row.setting_value is not None:
            values[row.setting_key] = row.setting_value
    return values


def _set_kv(publication: Publication, key: str, value: str | None) -> None:
    cleaned = (value or "").strip()
    existing = db.session.scalar(
        select(Setting).where(
            Setting.publication_id == publication.id,
            Setting.setting_key == key,
        )
    )
    if existing is None:
        db.session.add(
            Setting(
                publication_id=publication.id,
                setting_key=key,
                setting_value=cleaned,
            )
        )
        return
    existing.setting_value = cleaned


def _media_url(media: Media | None) -> str | None:
    if media is None or not media.path:
        return None
    return url_for("static", filename=media.path)


def _social_links(kv: dict[str, str]) -> list[dict[str, str]]:
    mapping = [
        ("social_twitter", "X / Twitter", "twitter"),
        ("social_linkedin", "LinkedIn", "linkedin"),
        ("social_facebook", "Facebook", "facebook"),
        ("social_instagram", "Instagram", "instagram"),
        ("social_youtube", "YouTube", "youtube"),
        ("social_substack", "Substack", "substack"),
    ]
    links = []
    for key, label, network in mapping:
        url = (kv.get(key) or "").strip()
        if url:
            links.append({"key": network, "label": label, "url": url})
    return links


def get_site_settings() -> SiteSettings:
    from flask import g, has_request_context

    if has_request_context() and getattr(g, "_site_settings", None) is not None:
        return g._site_settings

    publication = get_or_create_default_publication()
    # Ensure logo/banner are available
    publication = db.session.scalar(
        select(Publication)
        .options(
            joinedload(Publication.logo),
            joinedload(Publication.banner),
        )
        .where(Publication.id == publication.id)
    ) or publication

    kv = _load_kv(publication.id)
    primary = (
        (publication.primary_color or "").strip()
        or kv.get("theme_primary_color")
        or SETTING_DEFAULTS["theme_primary_color"]
    )
    settings = SiteSettings(
        publication_id=str(publication.id),
        name=publication.name,
        description=(publication.description or "").strip(),
        tagline=kv.get("tagline", SETTING_DEFAULTS["tagline"]),
        home_welcome=kv.get("home_welcome", SETTING_DEFAULTS["home_welcome"]),
        footer_blurb=kv.get("footer_blurb", SETTING_DEFAULTS["footer_blurb"]),
        footer_copyright=kv.get("footer_copyright", ""),
        contact_email=(
            kv.get("contact_email")
            or SETTING_DEFAULTS["contact_email"]
        ),
        contact_phone=kv.get("contact_phone", ""),
        contact_address=kv.get("contact_address", ""),
        social_twitter=kv.get("social_twitter", ""),
        social_linkedin=kv.get("social_linkedin", ""),
        social_facebook=kv.get("social_facebook", ""),
        social_instagram=kv.get("social_instagram", ""),
        social_youtube=kv.get("social_youtube", ""),
        social_substack=kv.get("social_substack", ""),
        google_site_verification=kv.get("google_site_verification", ""),
        primary_color=primary,
        logo_url=_media_url(publication.logo),
        logo_id=str(publication.logo_id) if publication.logo_id else None,
        banner_url=_media_url(publication.banner),
        social_links=_social_links(kv),
    )
    if has_request_context():
        g._site_settings = settings
    return settings


def save_site_settings_from_form(form, *, uploader) -> SiteSettings:
    publication = get_or_create_default_publication()
    publication = db.session.scalar(
        select(Publication)
        .options(joinedload(Publication.logo), joinedload(Publication.banner))
        .where(Publication.id == publication.id)
    ) or publication

    name = (form.site_name.data or "").strip()
    if not name:
        raise SettingsError("Site name is required.")

    color = (form.primary_color.data or "").strip() or SETTING_DEFAULTS["theme_primary_color"]
    if not _HEX_COLOR_RE.match(color):
        raise SettingsError("Primary color must be a hex value like #0f766e.")

    publication.name = name
    publication.description = (form.description.data or "").strip() or None
    publication.primary_color = color

    kv_fields = {
        "tagline": form.tagline.data,
        "home_welcome": form.home_welcome.data,
        "footer_blurb": form.footer_blurb.data,
        "footer_copyright": form.footer_copyright.data,
        "contact_email": form.contact_email.data,
        "contact_phone": form.contact_phone.data,
        "contact_address": form.contact_address.data,
        "social_twitter": form.social_twitter.data,
        "social_linkedin": form.social_linkedin.data,
        "social_facebook": form.social_facebook.data,
        "social_instagram": form.social_instagram.data,
        "social_youtube": form.social_youtube.data,
        "social_substack": form.social_substack.data,
        "google_site_verification": form.google_site_verification.data,
        "theme_primary_color": color,
    }
    for key, value in kv_fields.items():
        _set_kv(publication, key, value)

    if form.clear_logo.data:
        publication.logo_id = None
    elif form.logo_file.data and getattr(form.logo_file.data, "filename", None):
        try:
            media = save_image_upload(
                form.logo_file.data,
                uploader,
                alt_text=f"{name} logo",
            )
        except MediaUploadError as exc:
            raise SettingsError(str(exc)) from exc
        publication.logo_id = media.id

    log_activity("settings.updated", "Updated site settings")
    db.session.commit()
    return get_site_settings()
