"""Article CRUD and status transitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.forms.article import ArticleForm
from app.models import Article, ArticleStatus, Category, Tag, User
from app.services.media import MediaUploadError, save_image_upload
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity
from app.utils.html_sanitize import sanitize_article_html
from app.utils.reading_time import estimate_reading_time
from app.utils.slug import unique_article_slug


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def list_articles(status: str | None = None) -> list[Article]:
    stmt = (
        select(Article)
        .options(
            joinedload(Article.author),
            joinedload(Article.publication),
            joinedload(Article.featured_image_media),
            joinedload(Article.categories),
            joinedload(Article.tags),
        )
        .order_by(Article.updated_at.desc())
    )
    if status:
        try:
            stmt = stmt.where(Article.status == ArticleStatus(status.upper()))
        except ValueError:
            pass
    return list(db.session.scalars(stmt).unique().all())


def get_article(article_id: uuid.UUID) -> Article | None:
    stmt = (
        select(Article)
        .options(
            joinedload(Article.author),
            joinedload(Article.publication),
            joinedload(Article.featured_image_media),
            joinedload(Article.categories),
            joinedload(Article.tags),
        )
        .where(Article.id == article_id)
    )
    return db.session.scalars(stmt).unique().first()


def _parse_uuid_list(values: list[str] | None) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for value in values or []:
        try:
            ids.append(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return ids


def sync_article_taxonomy(article: Article, form: ArticleForm) -> None:
    """Replace article categories/tags from multi-select form values."""
    category_ids = _parse_uuid_list(form.categories.data)
    tag_ids = _parse_uuid_list(form.tags.data)

    if category_ids:
        categories = list(
            db.session.scalars(
                select(Category).where(
                    Category.id.in_(category_ids),
                    Category.publication_id == article.publication_id,
                )
            ).all()
        )
    else:
        categories = []

    if tag_ids:
        tags = list(
            db.session.scalars(
                select(Tag).where(
                    Tag.id.in_(tag_ids),
                    Tag.publication_id == article.publication_id,
                )
            ).all()
        )
    else:
        tags = []

    article.categories = categories
    article.tags = tags


def count_by_status() -> dict[str, int]:
    counts = {status.value: 0 for status in ArticleStatus}
    rows = db.session.execute(
        select(Article.status, func.count()).group_by(Article.status)
    ).all()
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = int(count)
    counts["ALL"] = sum(v for k, v in counts.items() if k != "ALL")
    return counts


def _save_featured_image(file: FileStorage, uploader: User):
    if not file or not file.filename:
        return None
    try:
        return save_image_upload(file, uploader)
    except MediaUploadError:
        return None


def apply_status_timestamps(article: Article) -> None:
    """Normalize publish/schedule timestamps based on status."""
    now = datetime.now(timezone.utc)
    if article.status == ArticleStatus.PUBLISHED:
        if article.published_at is None:
            article.published_at = now
        article.scheduled_at = None
    elif article.status == ArticleStatus.SCHEDULED:
        article.published_at = None
    elif article.status == ArticleStatus.DRAFT:
        pass
    elif article.status == ArticleStatus.ARCHIVED:
        pass


def save_article_from_form(
    form: ArticleForm,
    *,
    author: User,
    article: Article | None = None,
) -> Article:
    is_new = article is None

    if is_new:
        publication = get_or_create_default_publication()
        article = Article(
            publication_id=publication.id,
            author_id=author.id,
            title=form.title.data.strip(),
            slug="temp",
            featured=False,
            allow_comments=True,
        )
        db.session.add(article)
        publication_id = publication.id
    else:
        article.title = form.title.data.strip()
        publication_id = article.publication_id

    article.subtitle = (form.subtitle.data or "").strip() or None
    article.excerpt = (form.excerpt.data or "").strip() or None
    article.content = sanitize_article_html(form.content.data)
    article.seo_title = (form.seo_title.data or "").strip() or None
    article.seo_description = (form.seo_description.data or "").strip() or None
    article.canonical_url = (form.canonical_url.data or "").strip() or None
    article.featured = bool(form.featured.data)
    article.allow_comments = bool(form.allow_comments.data)
    article.status = ArticleStatus(form.status.data)
    article.published_at = _aware(form.published_at.data)
    article.scheduled_at = _aware(form.scheduled_at.data)

    article.slug = unique_article_slug(
        publication_id,
        article.title,
        desired=form.slug.data,
        exclude_id=None if is_new else article.id,
    )

    if form.reading_time.data is not None:
        article.reading_time = form.reading_time.data
    else:
        article.reading_time = estimate_reading_time(article.content)

    if form.clear_featured_image.data:
        article.featured_image = None
    elif form.featured_image_file.data:
        media = _save_featured_image(form.featured_image_file.data, author)
        if media is not None:
            article.featured_image = media.id

    sync_article_taxonomy(article, form)
    apply_status_timestamps(article)
    log_activity(
        "article.created" if is_new else "article.updated",
        f"{'Created' if is_new else 'Updated'} “{article.title}” ({article.status.value})",
    )
    db.session.commit()
    return article


def delete_article(article: Article) -> None:
    title = article.title
    log_activity("article.deleted", f"Deleted “{title}”")
    db.session.delete(article)
    db.session.commit()


def set_article_status(article: Article, status: ArticleStatus) -> Article:
    article.status = status
    if status == ArticleStatus.PUBLISHED and article.published_at is None:
        article.published_at = datetime.now(timezone.utc)
        article.scheduled_at = None
    if status == ArticleStatus.SCHEDULED and article.scheduled_at is None:
        raise ValueError("scheduled_at is required for scheduled articles")
    if status == ArticleStatus.DRAFT:
        pass
    apply_status_timestamps(article)
    log_activity(
        f"article.{status.value.lower()}",
        f"Set “{article.title}” to {status.value}",
    )
    db.session.commit()
    return article
