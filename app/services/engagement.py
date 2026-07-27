"""Public article comments and likes."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from flask import Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Article, ArticleLike, Comment
from app.models.enums import ArticleStatus
from app.utils.activity import log_activity
from app.utils.client_info import client_ip

VISITOR_COOKIE = "liminal_vid"
_VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 years


class EngagementError(ValueError):
    """Invalid engagement action."""


@dataclass
class LikeState:
    count: int
    liked: bool


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def ensure_visitor_key(request: Request, response: Response | None = None) -> str:
    """Return a stable visitor key; set cookie on response when provided."""
    existing = (request.cookies.get(VISITOR_COOKIE) or "").strip()
    if existing and len(existing) <= 64:
        return existing

    key = secrets.token_urlsafe(24)[:64]
    if response is not None:
        response.set_cookie(
            VISITOR_COOKIE,
            key,
            max_age=_VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=bool(request.is_secure),
        )
    return key


def visitor_key_from_request(request: Request) -> str:
    """Stable key for the current request (cookie or fingerprint fallback)."""
    cookie = (request.cookies.get(VISITOR_COOKIE) or "").strip()
    if cookie and len(cookie) <= 64:
        return cookie
    ip = client_ip(request) or "unknown"
    ua = (request.headers.get("User-Agent") or "")[:200]
    digest = hashlib.sha256(f"{ip}|{ua}".encode("utf-8")).hexdigest()[:48]
    return f"fp_{digest}"


def get_published_article(article_id: uuid.UUID) -> Article | None:
    return db.session.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.status == ArticleStatus.PUBLISHED,
        )
    )


def list_approved_comments(article_id: uuid.UUID) -> list[Comment]:
    return list(
        db.session.scalars(
            select(Comment)
            .where(
                Comment.article_id == article_id,
                Comment.approved.is_(True),
            )
            .order_by(Comment.created_at.asc())
        ).all()
    )


def submit_comment(
    article: Article,
    *,
    full_name: str,
    email: str,
    body: str,
) -> Comment:
    if not article.allow_comments:
        raise EngagementError("Comments are closed for this article.")

    name = (full_name or "").strip()
    text = (body or "").strip()
    mail = _normalize_email(email)
    if not name:
        raise EngagementError("Name is required.")
    if not mail:
        raise EngagementError("Email is required.")
    if not text:
        raise EngagementError("Comment cannot be empty.")
    if len(text) > 5000:
        raise EngagementError("Comment is too long.")

    comment = Comment(
        article_id=article.id,
        full_name=name[:150],
        email=mail[:150],
        comment=text,
        approved=False,
    )
    db.session.add(comment)
    db.session.commit()
    return comment


def like_state(article_id: uuid.UUID, visitor_key: str) -> LikeState:
    count = db.session.scalar(
        select(func.count())
        .select_from(ArticleLike)
        .where(ArticleLike.article_id == article_id)
    ) or 0
    liked = (
        db.session.scalar(
            select(ArticleLike.id).where(
                ArticleLike.article_id == article_id,
                ArticleLike.visitor_key == visitor_key,
            )
        )
        is not None
    )
    return LikeState(count=int(count), liked=liked)


def toggle_like(article: Article, visitor_key: str) -> LikeState:
    key = (visitor_key or "").strip()[:64]
    if not key:
        raise EngagementError("Unable to record like.")

    existing = db.session.scalar(
        select(ArticleLike).where(
            ArticleLike.article_id == article.id,
            ArticleLike.visitor_key == key,
        )
    )
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        return like_state(article.id, key)

    db.session.add(ArticleLike(article_id=article.id, visitor_key=key))
    db.session.commit()
    return like_state(article.id, key)


def list_comments_admin(
    *,
    status: str | None = None,
    q: str | None = None,
    limit: int = 200,
) -> list[Comment]:
    stmt = (
        select(Comment)
        .options(joinedload(Comment.article))
        .order_by(Comment.created_at.desc())
        .limit(limit)
    )
    if status == "pending":
        stmt = stmt.where(Comment.approved.is_(False))
    elif status == "approved":
        stmt = stmt.where(Comment.approved.is_(True))

    query = (q or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Comment.full_name.ilike(pattern),
                Comment.email.ilike(pattern),
                Comment.comment.ilike(pattern),
            )
        )
    return list(db.session.scalars(stmt).unique().all())


def count_comments_by_status() -> dict[str, int]:
    rows = db.session.execute(
        select(Comment.approved, func.count()).group_by(Comment.approved)
    ).all()
    pending = 0
    approved = 0
    for approved_flag, count in rows:
        if approved_flag:
            approved = int(count)
        else:
            pending = int(count)
    return {
        "ALL": pending + approved,
        "pending": pending,
        "approved": approved,
    }


def get_comment(comment_id: uuid.UUID) -> Comment | None:
    return db.session.scalar(
        select(Comment)
        .options(joinedload(Comment.article))
        .where(Comment.id == comment_id)
    )


def set_comment_approved(comment: Comment, *, approved: bool) -> Comment:
    comment.approved = approved
    log_activity(
        "comment.approved" if approved else "comment.unapproved",
        f"{'Approved' if approved else 'Unapproved'} comment on “{comment.article.title if comment.article else comment.article_id}”",
    )
    db.session.commit()
    return comment


def delete_comment(comment: Comment) -> None:
    title = comment.article.title if comment.article else str(comment.article_id)
    db.session.delete(comment)
    log_activity("comment.deleted", f"Deleted comment on “{title}”")
    db.session.commit()
