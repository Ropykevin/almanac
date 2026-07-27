"""Queries for the public-facing publication website."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Article, ArticleStatus, Category, Tag


def _published_options():
    return (
        joinedload(Article.author),
        joinedload(Article.featured_image_media),
        joinedload(Article.categories),
        joinedload(Article.tags),
        joinedload(Article.publication),
    )


def _keyword_filters(query: str | None) -> list:
    """AND-match keyword tokens across title, excerpt, and body fields."""
    q = (query or "").strip()
    if not q:
        return []
    tokens = [t for t in q.split() if t]
    filters = []
    for token in tokens:
        pattern = f"%{token}%"
        filters.append(
            or_(
                Article.title.ilike(pattern),
                Article.subtitle.ilike(pattern),
                Article.excerpt.ilike(pattern),
                Article.seo_title.ilike(pattern),
                Article.seo_description.ilike(pattern),
                Article.content.ilike(pattern),
            )
        )
    return filters


def list_published_articles(
    *,
    limit: int | None = None,
    offset: int = 0,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    query: str | None = None,
) -> list[Article]:
    stmt = (
        select(Article)
        .options(*_published_options())
        .where(Article.status == ArticleStatus.PUBLISHED)
        .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
    )
    if category_slug:
        stmt = stmt.join(Article.categories).where(Category.slug == category_slug)
    if tag_slug:
        stmt = stmt.join(Article.tags).where(Tag.slug == tag_slug)
    for filt in _keyword_filters(query):
        stmt = stmt.where(filt)
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.session.scalars(stmt).unique().all())


def count_published_articles(
    *,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    query: str | None = None,
) -> int:
    stmt = (
        select(func.count(func.distinct(Article.id)))
        .select_from(Article)
        .where(Article.status == ArticleStatus.PUBLISHED)
    )
    if category_slug:
        stmt = stmt.join(Article.categories).where(Category.slug == category_slug)
    if tag_slug:
        stmt = stmt.join(Article.tags).where(Tag.slug == tag_slug)
    for filt in _keyword_filters(query):
        stmt = stmt.where(filt)
    return int(db.session.scalar(stmt) or 0)


def get_published_article(slug: str) -> Article | None:
    stmt = (
        select(Article)
        .options(*_published_options())
        .where(
            Article.slug == slug,
            Article.status == ArticleStatus.PUBLISHED,
        )
    )
    return db.session.scalars(stmt).unique().first()


def get_featured_article() -> Article | None:
    stmt = (
        select(Article)
        .options(*_published_options())
        .where(
            Article.status == ArticleStatus.PUBLISHED,
            Article.featured.is_(True),
        )
        .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
        .limit(1)
    )
    featured = db.session.scalars(stmt).unique().first()
    if featured is not None:
        return featured
    latest = list_published_articles(limit=1)
    return latest[0] if latest else None


def related_articles(article: Article, *, limit: int = 3) -> list[Article]:
    category_ids = [c.id for c in article.categories]
    tag_ids = [t.id for t in article.tags]

    if not category_ids and not tag_ids:
        stmt = (
            select(Article)
            .options(*_published_options())
            .where(
                Article.status == ArticleStatus.PUBLISHED,
                Article.id != article.id,
            )
            .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
            .limit(limit)
        )
        return list(db.session.scalars(stmt).unique().all())

    filters = []
    if category_ids:
        filters.append(Category.id.in_(category_ids))
    if tag_ids:
        filters.append(Tag.id.in_(tag_ids))

    stmt = (
        select(Article)
        .options(*_published_options())
        .outerjoin(Article.categories)
        .outerjoin(Article.tags)
        .where(
            Article.status == ArticleStatus.PUBLISHED,
            Article.id != article.id,
            or_(*filters),
        )
        .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt).unique().all())


def _search_articles_postgres(query: str, *, limit: int) -> list[Article]:
    """PostgreSQL full-text search with ranked results + ILIKE fallback boost."""
    ts_vector = func.to_tsvector(
        "english",
        func.concat_ws(
            " ",
            Article.title,
            Article.subtitle,
            Article.excerpt,
            Article.seo_title,
            Article.seo_description,
            Article.content,
        ),
    )
    ts_query = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(ts_vector, ts_query)
    pattern = f"%{query}%"
    ilike_match = or_(
        Article.title.ilike(pattern),
        Article.subtitle.ilike(pattern),
        Article.excerpt.ilike(pattern),
        Article.seo_title.ilike(pattern),
        Article.seo_description.ilike(pattern),
        Article.content.ilike(pattern),
    )
    stmt = (
        select(Article, rank.label("rank"))
        .options(*_published_options())
        .where(
            Article.status == ArticleStatus.PUBLISHED,
            or_(ts_vector.op("@@")(ts_query), ilike_match),
        )
        .order_by(rank.desc(), func.coalesce(Article.published_at, Article.created_at).desc())
        .limit(limit)
    )
    rows = db.session.execute(stmt).unique().all()
    return [row[0] for row in rows]


def _search_articles_ilike(query: str, *, limit: int) -> list[Article]:
    """SQLite / generic full-text fallback using multi-column ILIKE."""
    # Split into tokens for broader matching (AND semantics across words).
    tokens = [t for t in query.split() if t]
    if not tokens:
        return []

    filters = []
    for token in tokens:
        pattern = f"%{token}%"
        filters.append(
            or_(
                Article.title.ilike(pattern),
                Article.subtitle.ilike(pattern),
                Article.excerpt.ilike(pattern),
                Article.seo_title.ilike(pattern),
                Article.seo_description.ilike(pattern),
                Article.content.ilike(pattern),
            )
        )

    stmt = (
        select(Article)
        .options(*_published_options())
        .where(Article.status == ArticleStatus.PUBLISHED, *filters)
        .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt).unique().all())


def search_articles(query: str, *, limit: int = 30) -> list[Article]:
    """Full-text search over published articles (Postgres FTS, else ILIKE)."""
    q = (query or "").strip()
    if not q:
        return []
    dialect = db.engine.dialect.name
    if dialect == "postgresql":
        return _search_articles_postgres(q, limit=limit)
    return _search_articles_ilike(q, limit=limit)


def list_sitemap_articles(*, limit: int = 5000) -> list[Article]:
    stmt = (
        select(Article)
        .where(Article.status == ArticleStatus.PUBLISHED)
        .order_by(func.coalesce(Article.published_at, Article.created_at).desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt).all())


def list_feed_articles(*, limit: int = 30) -> list[Article]:
    return list_published_articles(limit=limit)


def list_public_categories() -> list[Category]:
    stmt = (
        select(Category)
        .join(Category.articles)
        .where(Article.status == ArticleStatus.PUBLISHED)
        .order_by(Category.name.asc())
        .distinct()
    )
    return list(db.session.scalars(stmt).unique().all())
