"""Analytics aggregations and article view recording."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Request
from flask_login import current_user
from sqlalchemy import case, func, select
from app.extensions import db
from app.models import (
    Article,
    ArticleStatus,
    ArticleView,
    DeliveryStatus,
    Newsletter,
    NewsletterDelivery,
    NewsletterStatus,
    Subscriber,
    SubscriberStatus,
)
from app.utils.client_info import (
    client_ip,
    country_from_request,
    looks_like_bot,
    parse_browser,
)


@dataclass
class AnalyticsSnapshot:
    days: int
    total_views: int
    views_series: list[dict[str, Any]]
    subscriber_series: list[dict[str, Any]]
    subscriber_totals: dict[str, int]
    newsletter_summary: dict[str, int | float]
    newsletter_campaigns: list[dict[str, Any]]
    most_read: list[dict[str, Any]]
    countries: list[dict[str, Any]]
    reading_time: dict[str, Any]
    browsers: list[dict[str, Any]] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _since(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _day_label(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def record_article_view(article: Article, request: Request) -> ArticleView | None:
    """Persist a public article view. Skips bots and authenticated staff."""
    if current_user is not None and getattr(current_user, "is_authenticated", False):
        return None
    ua = request.headers.get("User-Agent")
    if looks_like_bot(ua):
        return None

    view = ArticleView(
        article_id=article.id,
        ip_address=client_ip(request),
        country=country_from_request(request),
        browser=parse_browser(ua),
        viewed_at=_now(),
    )
    db.session.add(view)
    db.session.commit()
    return view


def _fill_daily_series(
    rows: list[tuple[Any, int]],
    *,
    days: int,
) -> list[dict[str, Any]]:
    by_day = {_day_label(day): int(count) for day, count in rows if day is not None}
    series: list[dict[str, Any]] = []
    start = (_now() - timedelta(days=days - 1)).date()
    for offset in range(days):
        day = start + timedelta(days=offset)
        key = day.isoformat()
        series.append({"date": key, "count": by_day.get(key, 0)})
    return series


def article_views_series(days: int = 30) -> list[dict[str, Any]]:
    since = _since(days)
    day_col = func.date(ArticleView.viewed_at)
    rows = db.session.execute(
        select(day_col, func.count())
        .where(ArticleView.viewed_at >= since)
        .group_by(day_col)
        .order_by(day_col)
    ).all()
    return _fill_daily_series(rows, days=days)


def subscriber_growth_series(days: int = 30) -> list[dict[str, Any]]:
    since = _since(days)
    day_col = func.date(Subscriber.subscribed_at)
    rows = db.session.execute(
        select(day_col, func.count())
        .where(
            Subscriber.subscribed_at.is_not(None),
            Subscriber.subscribed_at >= since,
        )
        .group_by(day_col)
        .order_by(day_col)
    ).all()
    return _fill_daily_series(rows, days=days)


def subscriber_status_totals() -> dict[str, int]:
    totals = {s.value: 0 for s in SubscriberStatus}
    rows = db.session.execute(
        select(Subscriber.status, func.count()).group_by(Subscriber.status)
    ).all()
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        totals[key] = int(count)
    totals["ALL"] = sum(v for k, v in totals.items() if k != "ALL")
    return totals


def newsletter_performance(limit: int = 8) -> tuple[dict[str, int | float], list[dict[str, Any]]]:
    sent_statuses = (
        DeliveryStatus.SENT,
        DeliveryStatus.OPENED,
        DeliveryStatus.CLICKED,
    )
    total_sent = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(NewsletterDelivery.status.in_(sent_statuses))
    ) or 0
    total_opened = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(NewsletterDelivery.opened_at.is_not(None))
    ) or 0
    total_clicked = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(NewsletterDelivery.clicked_at.is_not(None))
    ) or 0
    total_failed = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(NewsletterDelivery.status == DeliveryStatus.FAILED)
    ) or 0
    campaigns_sent = db.session.scalar(
        select(func.count())
        .select_from(Newsletter)
        .where(Newsletter.status == NewsletterStatus.SENT)
    ) or 0

    open_rate = round((total_opened / total_sent) * 100, 1) if total_sent else 0.0
    click_rate = round((total_clicked / total_sent) * 100, 1) if total_sent else 0.0

    summary: dict[str, int | float] = {
        "campaigns_sent": int(campaigns_sent),
        "sent": int(total_sent),
        "opened": int(total_opened),
        "clicked": int(total_clicked),
        "failed": int(total_failed),
        "open_rate": open_rate,
        "click_rate": click_rate,
    }

    # Per-campaign breakdown for recent sent newsletters
    newsletters = list(
        db.session.scalars(
            select(Newsletter)
            .where(Newsletter.status == NewsletterStatus.SENT)
            .order_by(Newsletter.sent_at.desc(), Newsletter.created_at.desc())
            .limit(limit)
        ).all()
    )
    campaigns: list[dict[str, Any]] = []
    for item in newsletters:
        stats_rows = db.session.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case(
                        (NewsletterDelivery.opened_at.is_not(None), 1),
                        else_=0,
                    )
                ).label("opened"),
                func.sum(
                    case(
                        (NewsletterDelivery.clicked_at.is_not(None), 1),
                        else_=0,
                    )
                ).label("clicked"),
                func.sum(
                    case(
                        (
                            NewsletterDelivery.status.in_(sent_statuses),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sent"),
            ).where(NewsletterDelivery.newsletter_id == item.id)
        ).one()
        sent = int(stats_rows.sent or 0)
        opened = int(stats_rows.opened or 0)
        clicked = int(stats_rows.clicked or 0)
        campaigns.append(
            {
                "id": str(item.id),
                "subject": item.subject,
                "sent_at": item.sent_at,
                "sent": sent,
                "opened": opened,
                "clicked": clicked,
                "open_rate": round((opened / sent) * 100, 1) if sent else 0.0,
                "click_rate": round((clicked / sent) * 100, 1) if sent else 0.0,
            }
        )
    return summary, campaigns


def most_read_articles(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    since = _since(days)
    rows = db.session.execute(
        select(
            Article.id,
            Article.title,
            Article.slug,
            Article.reading_time,
            func.count(ArticleView.id).label("views"),
        )
        .join(ArticleView, ArticleView.article_id == Article.id)
        .where(ArticleView.viewed_at >= since)
        .group_by(Article.id, Article.title, Article.slug, Article.reading_time)
        .order_by(func.count(ArticleView.id).desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "slug": row.slug,
            "reading_time": row.reading_time or 0,
            "views": int(row.views),
        }
        for row in rows
    ]


def countries_breakdown(days: int = 30, limit: int = 12) -> list[dict[str, Any]]:
    since = _since(days)
    # Reuse one expression so Postgres GROUP BY matches SELECT (avoid dual binds).
    country_col = func.coalesce(ArticleView.country, "Unknown").label("country")
    rows = db.session.execute(
        select(country_col, func.count().label("views"))
        .where(ArticleView.viewed_at >= since)
        .group_by(country_col)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [{"country": row.country, "views": int(row.views)} for row in rows]


def browsers_breakdown(days: int = 30, limit: int = 8) -> list[dict[str, Any]]:
    since = _since(days)
    browser_col = func.coalesce(ArticleView.browser, "Unknown").label("browser")
    rows = db.session.execute(
        select(browser_col, func.count().label("views"))
        .where(ArticleView.viewed_at >= since)
        .group_by(browser_col)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [{"browser": row.browser, "views": int(row.views)} for row in rows]


def reading_time_stats() -> dict[str, Any]:
    published = Article.status == ArticleStatus.PUBLISHED
    avg_rt = db.session.scalar(
        select(func.avg(Article.reading_time)).where(
            published,
            Article.reading_time.is_not(None),
        )
    )
    min_rt = db.session.scalar(
        select(func.min(Article.reading_time)).where(
            published,
            Article.reading_time.is_not(None),
        )
    )
    max_rt = db.session.scalar(
        select(func.max(Article.reading_time)).where(
            published,
            Article.reading_time.is_not(None),
        )
    )
    count_published = db.session.scalar(
        select(func.count()).select_from(Article).where(published)
    ) or 0

    buckets = [
        ("1–3 min", 1, 3),
        ("4–6 min", 4, 6),
        ("7–10 min", 7, 10),
        ("11+ min", 11, 10_000),
    ]
    distribution: list[dict[str, Any]] = []
    for label, low, high in buckets:
        count = db.session.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                published,
                Article.reading_time.is_not(None),
                Article.reading_time >= low,
                Article.reading_time <= high,
            )
        ) or 0
        distribution.append({"label": label, "count": int(count)})

    top_long = list(
        db.session.scalars(
            select(Article)
            .where(published, Article.reading_time.is_not(None))
            .order_by(Article.reading_time.desc())
            .limit(5)
        ).all()
    )

    return {
        "average": round(float(avg_rt), 1) if avg_rt is not None else 0.0,
        "min": int(min_rt or 0),
        "max": int(max_rt or 0),
        "published_count": int(count_published),
        "distribution": distribution,
        "longest": [
            {
                "title": a.title,
                "slug": a.slug,
                "reading_time": a.reading_time or 0,
            }
            for a in top_long
        ],
    }


def total_views(days: int = 30) -> int:
    since = _since(days)
    return int(
        db.session.scalar(
            select(func.count())
            .select_from(ArticleView)
            .where(ArticleView.viewed_at >= since)
        )
        or 0
    )


def get_analytics_snapshot(days: int = 30) -> AnalyticsSnapshot:
    days = max(7, min(int(days), 90))
    nl_summary, nl_campaigns = newsletter_performance()
    return AnalyticsSnapshot(
        days=days,
        total_views=total_views(days),
        views_series=article_views_series(days),
        subscriber_series=subscriber_growth_series(days),
        subscriber_totals=subscriber_status_totals(),
        newsletter_summary=nl_summary,
        newsletter_campaigns=nl_campaigns,
        most_read=most_read_articles(days),
        countries=countries_breakdown(days),
        reading_time=reading_time_stats(),
        browsers=browsers_breakdown(days),
    )
