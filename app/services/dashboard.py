"""Dashboard metrics for the admin console."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    ActivityLog,
    Article,
    ArticleStatus,
    Newsletter,
    Subscriber,
    SubscriberStatus,
)


@dataclass(frozen=True)
class DashboardStats:
    total_articles: int
    draft_articles: int
    published_articles: int
    subscribers: int
    newsletter_campaigns: int


def get_dashboard_stats() -> DashboardStats:
    """Aggregate publishing metrics for the dashboard cards."""
    total_articles = db.session.scalar(select(func.count()).select_from(Article)) or 0
    draft_articles = (
        db.session.scalar(
            select(func.count()).select_from(Article).where(Article.status == ArticleStatus.DRAFT)
        )
        or 0
    )
    published_articles = (
        db.session.scalar(
            select(func.count())
            .select_from(Article)
            .where(Article.status == ArticleStatus.PUBLISHED)
        )
        or 0
    )
    subscribers = (
        db.session.scalar(
            select(func.count())
            .select_from(Subscriber)
            .where(Subscriber.status == SubscriberStatus.ACTIVE)
        )
        or 0
    )
    newsletter_campaigns = (
        db.session.scalar(select(func.count()).select_from(Newsletter)) or 0
    )

    return DashboardStats(
        total_articles=total_articles,
        draft_articles=draft_articles,
        published_articles=published_articles,
        subscribers=subscribers,
        newsletter_campaigns=newsletter_campaigns,
    )


def get_recent_activity(limit: int = 10) -> list[ActivityLog]:
    """Return newest activity log rows with actor loaded."""
    stmt = (
        select(ActivityLog)
        .options(joinedload(ActivityLog.user))
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt).unique().all())
