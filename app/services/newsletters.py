"""Newsletter campaign lifecycle: compose, preview, schedule, send, track."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import render_template, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Article,
    ArticleStatus,
    DeliveryStatus,
    Newsletter,
    NewsletterDelivery,
    NewsletterStatus,
    Subscriber,
    SubscriberStatus,
)
from app.services.articles import get_article
from app.services.publications import get_or_create_default_publication
from app.services import subscribers as subscriber_service
from app.utils.activity import log_activity
from app.utils.email import MailNotConfiguredError, MailSendError, mail_is_configured, send_html_email
from app.utils.html_sanitize import sanitize_article_html
from app.utils.tokens import generate_click_token, generate_open_token

_HREF_RE = re.compile(r"""href=(['"])(https?://.*?)\1""", re.IGNORECASE)


class NewsletterError(ValueError):
    """Domain error for newsletter operations."""


def _require_mail() -> None:
    if not mail_is_configured():
        raise NewsletterError(
            "Outbound mail is not configured. Set MAIL_SERVER, MAIL_USERNAME, "
            "MAIL_PASSWORD, and MAIL_DEFAULT_SENDER in .env "
            "(Brevo: smtp-relay.brevo.com), then restart the app."
        )

def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_newsletter(newsletter_id: uuid.UUID) -> Newsletter | None:
    stmt = (
        select(Newsletter)
        .options(
            joinedload(Newsletter.article).joinedload(Article.featured_image_media),
            joinedload(Newsletter.article).joinedload(Article.author),
            joinedload(Newsletter.publication),
        )
        .where(Newsletter.id == newsletter_id)
    )
    return db.session.scalars(stmt).unique().first()


def list_newsletters(status: str | None = None) -> list[Newsletter]:
    publication = get_or_create_default_publication()
    stmt = (
        select(Newsletter)
        .options(joinedload(Newsletter.article))
        .where(Newsletter.publication_id == publication.id)
        .order_by(Newsletter.created_at.desc())
    )
    if status:
        try:
            stmt = stmt.where(Newsletter.status == NewsletterStatus(status.upper()))
        except ValueError:
            pass
    return list(db.session.scalars(stmt).unique().all())


def list_sent_newsletters(*, limit: int = 24) -> list[Newsletter]:
    """Public archive of previously sent newsletters."""
    publication = get_or_create_default_publication()
    stmt = (
        select(Newsletter)
        .options(joinedload(Newsletter.article))
        .where(
            Newsletter.publication_id == publication.id,
            Newsletter.status == NewsletterStatus.SENT,
        )
        .order_by(
            func.coalesce(Newsletter.sent_at, Newsletter.created_at).desc(),
            Newsletter.created_at.desc(),
        )
        .limit(limit)
    )
    return list(db.session.scalars(stmt).unique().all())


def get_sent_newsletter(newsletter_id: uuid.UUID) -> Newsletter | None:
    publication = get_or_create_default_publication()
    return db.session.scalars(
        select(Newsletter)
        .options(joinedload(Newsletter.article))
        .where(
            Newsletter.id == newsletter_id,
            Newsletter.publication_id == publication.id,
            Newsletter.status == NewsletterStatus.SENT,
        )
    ).unique().first()


def count_by_status() -> dict[str, int]:
    publication = get_or_create_default_publication()
    counts = {s.value: 0 for s in NewsletterStatus}
    rows = db.session.execute(
        select(Newsletter.status, func.count())
        .where(Newsletter.publication_id == publication.id)
        .group_by(Newsletter.status)
    ).all()
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = int(count)
    counts["ALL"] = sum(v for k, v in counts.items() if k != "ALL")
    return counts


def article_choices() -> list[tuple[str, str]]:
    publication = get_or_create_default_publication()
    articles = db.session.scalars(
        select(Article)
        .where(
            Article.publication_id == publication.id,
            Article.status == ArticleStatus.PUBLISHED,
        )
        .order_by(Article.published_at.desc(), Article.title.asc())
    ).all()
    choices = [("", "— No article —")]
    for article in articles:
        choices.append((str(article.id), article.title))
    return choices


def delivery_stats(newsletter_id: uuid.UUID) -> dict[str, int]:
    rows = db.session.execute(
        select(NewsletterDelivery.status, func.count())
        .where(NewsletterDelivery.newsletter_id == newsletter_id)
        .group_by(NewsletterDelivery.status)
    ).all()
    by_status = {s.value: 0 for s in DeliveryStatus}
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        by_status[key] = int(count)

    opened = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(
            NewsletterDelivery.newsletter_id == newsletter_id,
            NewsletterDelivery.opened_at.is_not(None),
        )
    ) or 0
    clicked = db.session.scalar(
        select(func.count())
        .select_from(NewsletterDelivery)
        .where(
            NewsletterDelivery.newsletter_id == newsletter_id,
            NewsletterDelivery.clicked_at.is_not(None),
        )
    ) or 0
    sent = (
        by_status[DeliveryStatus.SENT.value]
        + by_status[DeliveryStatus.OPENED.value]
        + by_status[DeliveryStatus.CLICKED.value]
    )
    return {
        "sent": sent,
        "delivered": sent,  # SMTP accept = delivered (no ESP webhook in schema)
        "opened": int(opened),
        "clicked": int(clicked),
        "failed": by_status[DeliveryStatus.FAILED.value],
        "pending": by_status[DeliveryStatus.PENDING.value],
        "total": sum(by_status.values()),
    }


def _article_image_url(article: Article | None) -> str | None:
    if article is None or article.featured_image_media is None:
        return None
    return url_for(
        "static",
        filename=article.featured_image_media.path,
        _external=True,
    )


def build_campaign_html(
    *,
    subject: str,
    article: Article | None = None,
    custom_html: str | None = None,
    unsubscribe_url: str | None = None,
    open_pixel_url: str | None = None,
) -> str:
    """Render the responsive newsletter HTML shell."""
    from flask import current_app

    app_name = current_app.config.get("APP_NAME", "Africa’s AI Almanac")
    if article is not None:
        headline = article.title
        dek = article.excerpt or article.subtitle or ""
        body_html = custom_html or article.content or ""
        cta_url = url_for("main.article_detail", slug=article.slug, _external=True)
        cta_label = "Read the full story"
        image_url = _article_image_url(article)
        eyebrow = "New from the publication"
    else:
        headline = subject
        dek = ""
        body_html = custom_html or ""
        cta_url = url_for("main.index", _external=True)
        cta_label = "Visit the site"
        image_url = None
        eyebrow = "Newsletter"

    # Always sanitize email HTML (article content or custom campaign body).
    if body_html:
        body_html = sanitize_article_html(body_html) or ""

    return render_template(
        "emails/newsletter.html",
        app_name=app_name,
        subject=subject,
        eyebrow=eyebrow,
        headline=headline,
        dek=dek,
        body_html=body_html,
        image_url=image_url,
        cta_url=cta_url,
        cta_label=cta_label,
        unsubscribe_url=unsubscribe_url,
        open_pixel_url=open_pixel_url,
    )


def inject_tracking(html: str, delivery: NewsletterDelivery) -> str:
    """Wrap http(s) links for click tracking and ensure open pixel is present."""
    delivery_id = str(delivery.id)
    open_token = generate_open_token(delivery_id)
    open_url = url_for("main.newsletter_open", token=open_token, _external=True)

    def _replace(match: re.Match[str]) -> str:
        quote, url = match.group(1), match.group(2)
        lower = url.lower()
        if any(
            part in lower
            for part in ("/unsubscribe", "/n/o/", "/n/c/", "mailto:")
        ):
            return match.group(0)
        token = generate_click_token(delivery_id, url)
        tracked = url_for("main.newsletter_click", token=token, _external=True)
        return f"href={quote}{tracked}{quote}"

    tracked_html = _HREF_RE.sub(_replace, html)
    pixel = (
        f'<img src="{open_url}" width="1" height="1" alt="" '
        f'style="display:none;width:1px;height:1px;border:0;">'
    )
    if "</body>" in tracked_html.lower():
        # Case-insensitive insert before </body>
        return re.sub(
            r"</body>",
            pixel + "</body>",
            tracked_html,
            count=1,
            flags=re.IGNORECASE,
        )
    return tracked_html + pixel


def preview_html(newsletter: Newsletter) -> str:
    article = newsletter.article
    if article is None and newsletter.article_id:
        article = get_article(newsletter.article_id)
    return build_campaign_html(
        subject=newsletter.subject,
        article=article,
        custom_html=newsletter.html_content,
        unsubscribe_url=url_for("main.unsubscribe", _external=True),
    )


def save_newsletter_from_form(form, *, newsletter: Newsletter | None = None) -> Newsletter:
    publication = get_or_create_default_publication()
    article_id_raw = (form.article_id.data or "").strip()
    article_id = uuid.UUID(article_id_raw) if article_id_raw else None
    article = get_article(article_id) if article_id else None
    if article_id and article is None:
        raise NewsletterError("Selected article was not found.")

    subject = form.subject.data.strip()
    raw_html = (form.html_content.data or "").strip() or None
    custom_html = sanitize_article_html(raw_html) if raw_html else None

    if newsletter is None:
        newsletter = Newsletter(
            publication_id=publication.id,
            status=NewsletterStatus.DRAFT,
        )
        db.session.add(newsletter)
        action = "newsletter.created"
    else:
        if newsletter.status == NewsletterStatus.SENDING:
            raise NewsletterError("Wait until sending finishes before editing this campaign.")
        action = "newsletter.updated"

    newsletter.subject = subject
    newsletter.article_id = article_id
    newsletter.html_content = custom_html

    log_activity(action, f"Newsletter “{subject}”")
    db.session.commit()
    return newsletter


def schedule_newsletter(newsletter: Newsletter, when: datetime) -> Newsletter:
    _require_mail()
    if newsletter.status not in (NewsletterStatus.DRAFT, NewsletterStatus.SCHEDULED):
        raise NewsletterError("Only draft or scheduled campaigns can be scheduled.")
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when <= _now():
        raise NewsletterError("Schedule time must be in the future.")
    newsletter.status = NewsletterStatus.SCHEDULED
    newsletter.scheduled_at = when
    log_activity("newsletter.scheduled", f"Scheduled “{newsletter.subject}” for {when.isoformat()}")
    db.session.commit()
    return newsletter


def cancel_schedule(newsletter: Newsletter) -> Newsletter:
    if newsletter.status != NewsletterStatus.SCHEDULED:
        raise NewsletterError("Campaign is not scheduled.")
    newsletter.status = NewsletterStatus.DRAFT
    newsletter.scheduled_at = None
    log_activity("newsletter.schedule_cancelled", f"Unscheduled “{newsletter.subject}”")
    db.session.commit()
    return newsletter


def delete_newsletter(newsletter: Newsletter) -> None:
    subject = newsletter.subject
    status = newsletter.status.value
    log_activity("newsletter.deleted", f"Deleted newsletter “{subject}” ({status})")
    db.session.delete(newsletter)
    db.session.commit()


def _active_subscribers(publication_id: uuid.UUID) -> list[Subscriber]:
    return list(
        db.session.scalars(
            select(Subscriber).where(
                Subscriber.publication_id == publication_id,
                Subscriber.status == SubscriberStatus.ACTIVE,
            )
        ).all()
    )


def _ensure_delivery(newsletter: Newsletter, subscriber: Subscriber) -> NewsletterDelivery:
    existing = db.session.scalar(
        select(NewsletterDelivery).where(
            NewsletterDelivery.newsletter_id == newsletter.id,
            NewsletterDelivery.subscriber_id == subscriber.id,
        )
    )
    if existing is not None:
        return existing
    delivery = NewsletterDelivery(
        newsletter_id=newsletter.id,
        subscriber_id=subscriber.id,
        status=DeliveryStatus.PENDING,
    )
    db.session.add(delivery)
    db.session.flush()
    return delivery


def _render_for_subscriber(
    newsletter: Newsletter,
    subscriber: Subscriber,
    delivery: NewsletterDelivery,
) -> str:
    article = newsletter.article
    if article is None and newsletter.article_id:
        article = get_article(newsletter.article_id)
    unsub = subscriber_service.unsubscribe_link_for(subscriber)
    html = build_campaign_html(
        subject=newsletter.subject,
        article=article,
        custom_html=newsletter.html_content,
        unsubscribe_url=unsub,
    )
    return inject_tracking(html, delivery)


def send_test_email(newsletter: Newsletter, to_email: str) -> None:
    _require_mail()
    to_email = to_email.strip().lower()
    if not to_email or "@" not in to_email:
        raise NewsletterError("Enter a valid test email address.")
    article = newsletter.article
    if article is None and newsletter.article_id:
        article = get_article(newsletter.article_id)
    html = build_campaign_html(
        subject=f"[TEST] {newsletter.subject}",
        article=article,
        custom_html=newsletter.html_content,
        unsubscribe_url=url_for("main.unsubscribe", _external=True),
    )
    try:
        send_html_email(
            to_email=to_email,
            subject=f"[TEST] {newsletter.subject}",
            html_body=html,
            require_smtp=True,
        )
    except (MailNotConfiguredError, MailSendError) as exc:
        raise NewsletterError(str(exc)) from exc
    except OSError as exc:
        raise NewsletterError(f"Could not send test email: {exc}") from exc
    log_activity("newsletter.test_sent", f"Test for “{newsletter.subject}” → {to_email}")
    db.session.commit()


def send_newsletter_now(newsletter: Newsletter) -> dict[str, int | list[str]]:
    if newsletter.status in (NewsletterStatus.SENDING, NewsletterStatus.SENT):
        raise NewsletterError("This campaign has already been sent.")

    _require_mail()

    newsletter.status = NewsletterStatus.SENDING
    db.session.commit()

    subscribers = _active_subscribers(newsletter.publication_id)
    stats: dict[str, int | list[str]] = {
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }
    if not subscribers:
        newsletter.status = NewsletterStatus.SENT
        newsletter.sent_at = _now()
        log_activity(
            "newsletter.sent",
            f"Sent “{newsletter.subject}” to 0 subscribers",
        )
        db.session.commit()
        return stats

    for subscriber in subscribers:
        delivery = _ensure_delivery(newsletter, subscriber)
        if delivery.status in (
            DeliveryStatus.SENT,
            DeliveryStatus.OPENED,
            DeliveryStatus.CLICKED,
        ):
            stats["skipped"] = int(stats["skipped"]) + 1
            continue
        try:
            html = _render_for_subscriber(newsletter, subscriber, delivery)
            send_html_email(
                to_email=subscriber.email,
                subject=newsletter.subject,
                html_body=html,
                require_smtp=True,
            )
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = _now()
            delivery.error_message = None
            stats["sent"] = int(stats["sent"]) + 1
        except MailNotConfiguredError as exc:
            newsletter.status = NewsletterStatus.DRAFT
            newsletter.sent_at = None
            db.session.commit()
            raise NewsletterError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — isolate per-recipient failures
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(exc)[:2000]
            stats["failed"] = int(stats["failed"]) + 1
            errors = stats["errors"]
            assert isinstance(errors, list)
            errors.append(f"{subscriber.email}: {exc}")
            from flask import current_app

            current_app.logger.exception(
                "Newsletter delivery failed for %s: %s",
                subscriber.email,
                exc,
            )
        db.session.commit()

    newsletter.status = NewsletterStatus.SENT
    newsletter.sent_at = _now()
    log_activity(
        "newsletter.sent",
        f"Sent “{newsletter.subject}” sent={stats['sent']} failed={stats['failed']}",
    )
    db.session.commit()
    return stats


def retry_failed_deliveries(newsletter: Newsletter) -> dict[str, int | list[str]]:
    """Re-attempt FAILED deliveries for an already-sent campaign."""
    if newsletter.status != NewsletterStatus.SENT:
        raise NewsletterError("Only sent campaigns can retry failed deliveries.")
    _require_mail()

    failed = list(
        db.session.scalars(
            select(NewsletterDelivery)
            .options(joinedload(NewsletterDelivery.subscriber))
            .where(
                NewsletterDelivery.newsletter_id == newsletter.id,
                NewsletterDelivery.status == DeliveryStatus.FAILED,
            )
        ).unique().all()
    )
    stats: dict[str, int | list[str]] = {
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }
    if not failed:
        raise NewsletterError("No failed deliveries to retry.")

    for delivery in failed:
        subscriber = delivery.subscriber
        if subscriber is None or subscriber.status != SubscriberStatus.ACTIVE:
            stats["skipped"] = int(stats["skipped"]) + 1
            continue
        try:
            html = _render_for_subscriber(newsletter, subscriber, delivery)
            send_html_email(
                to_email=subscriber.email,
                subject=newsletter.subject,
                html_body=html,
                require_smtp=True,
            )
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = _now()
            delivery.error_message = None
            stats["sent"] = int(stats["sent"]) + 1
        except Exception as exc:  # noqa: BLE001
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(exc)[:2000]
            stats["failed"] = int(stats["failed"]) + 1
            errors = stats["errors"]
            assert isinstance(errors, list)
            errors.append(f"{subscriber.email}: {exc}")
            from flask import current_app

            current_app.logger.exception(
                "Newsletter retry failed for %s: %s",
                subscriber.email,
                exc,
            )
        db.session.commit()

    log_activity(
        "newsletter.retry",
        f"Retry “{newsletter.subject}” sent={stats['sent']} failed={stats['failed']}",
    )
    db.session.commit()
    return stats


def process_due_newsletters() -> int:
    """Send campaigns whose schedule time has arrived. Returns count processed."""
    due = list(
        db.session.scalars(
            select(Newsletter).where(
                Newsletter.status == NewsletterStatus.SCHEDULED,
                Newsletter.scheduled_at.is_not(None),
                Newsletter.scheduled_at <= _now(),
            )
        ).all()
    )
    for newsletter in due:
        send_newsletter_now(newsletter)
    return len(due)


def record_open(delivery_id: uuid.UUID) -> NewsletterDelivery | None:
    delivery = db.session.get(NewsletterDelivery, delivery_id)
    if delivery is None:
        return None
    if delivery.opened_at is None:
        delivery.opened_at = _now()
    if delivery.status in (DeliveryStatus.PENDING, DeliveryStatus.SENT):
        delivery.status = DeliveryStatus.OPENED
    db.session.commit()
    return delivery


def record_click(delivery_id: uuid.UUID, url: str) -> str | None:
    """Record click and return safe redirect URL, or None if rejected."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    delivery = db.session.get(NewsletterDelivery, delivery_id)
    if delivery is None:
        return url
    if delivery.clicked_at is None:
        delivery.clicked_at = _now()
    if delivery.opened_at is None:
        delivery.opened_at = _now()
    if delivery.status != DeliveryStatus.FAILED:
        delivery.status = DeliveryStatus.CLICKED
    db.session.commit()
    return url


def list_deliveries(newsletter_id: uuid.UUID, limit: int = 100) -> list[NewsletterDelivery]:
    stmt = (
        select(NewsletterDelivery)
        .options(joinedload(NewsletterDelivery.subscriber))
        .where(NewsletterDelivery.newsletter_id == newsletter_id)
        .order_by(NewsletterDelivery.sent_at.desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt).unique().all())
