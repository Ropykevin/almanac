"""Slug generation helpers."""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import Article, Category, Tag


def slugify(value: str, *, fallback: str = "item") -> str:
    """Convert text to a URL-safe slug."""
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value).strip("-")
    return value or fallback


def _unique_scoped_slug(
    model,
    publication_id: uuid.UUID,
    source: str,
    *,
    desired: str | None = None,
    exclude_id: uuid.UUID | None = None,
    fallback: str = "item",
) -> str:
    base = slugify(desired or source, fallback=fallback)
    candidate = base
    counter = 2

    while True:
        stmt = select(model.id).where(
            model.publication_id == publication_id,
            model.slug == candidate,
        )
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        exists = db.session.scalar(stmt) is not None
        if not exists:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def unique_article_slug(
    publication_id: uuid.UUID,
    title: str,
    *,
    desired: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> str:
    """Return an article slug unique within a publication."""
    return _unique_scoped_slug(
        Article,
        publication_id,
        title,
        desired=desired,
        exclude_id=exclude_id,
        fallback="article",
    )


def unique_category_slug(
    publication_id: uuid.UUID,
    name: str,
    *,
    desired: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> str:
    return _unique_scoped_slug(
        Category,
        publication_id,
        name,
        desired=desired,
        exclude_id=exclude_id,
        fallback="category",
    )


def unique_tag_slug(
    publication_id: uuid.UUID,
    name: str,
    *,
    desired: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> str:
    return _unique_scoped_slug(
        Tag,
        publication_id,
        name,
        desired=desired,
        exclude_id=exclude_id,
        fallback="tag",
    )


def unique_project_slug(
    publication_id: uuid.UUID,
    title: str,
    *,
    desired: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> str:
    from app.models import Project

    return _unique_scoped_slug(
        Project,
        publication_id,
        title,
        desired=desired,
        exclude_id=exclude_id,
        fallback="project",
    )
