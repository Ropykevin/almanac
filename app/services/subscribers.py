"""Subscriber lifecycle: subscribe, verify, unsubscribe, CSV, admin ops."""

from __future__ import annotations

import csv
import io
import secrets
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import Subscriber, SubscriberStatus
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity
from app.utils.email import (
    MailNotConfiguredError,
    MailSendError,
    send_subscription_verification_email,
    send_unsubscribe_confirmation_email,
)
from app.utils.tokens import generate_unsubscribe_token, verify_unsubscribe_token


class SubscriberError(ValueError):
    """Domain error for subscriber operations."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _new_verification_token() -> str:
    return secrets.token_urlsafe(32)


def get_subscriber(subscriber_id: uuid.UUID) -> Subscriber | None:
    return db.session.get(Subscriber, subscriber_id)


def find_by_email(email: str, publication_id: uuid.UUID | None = None) -> Subscriber | None:
    if publication_id is None:
        publication_id = get_or_create_default_publication().id
    return db.session.scalar(
        select(Subscriber).where(
            Subscriber.publication_id == publication_id,
            Subscriber.email == _normalize_email(email),
        )
    )


def list_subscribers(
    *,
    status: str | None = None,
    q: str | None = None,
) -> list[Subscriber]:
    publication = get_or_create_default_publication()
    stmt = (
        select(Subscriber)
        .where(Subscriber.publication_id == publication.id)
        .order_by(
            func.coalesce(Subscriber.subscribed_at, Subscriber.unsubscribed_at).desc(),
            Subscriber.email.asc(),
        )
    )
    if status:
        try:
            stmt = stmt.where(Subscriber.status == SubscriberStatus(status.upper()))
        except ValueError:
            pass
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Subscriber.email.ilike(pattern),
                Subscriber.full_name.ilike(pattern),
            )
        )
    return list(db.session.scalars(stmt).all())


def count_by_status() -> dict[str, int]:
    publication = get_or_create_default_publication()
    counts = {s.value: 0 for s in SubscriberStatus}
    rows = db.session.execute(
        select(Subscriber.status, func.count())
        .where(Subscriber.publication_id == publication.id)
        .group_by(Subscriber.status)
    ).all()
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = int(count)
    counts["ALL"] = sum(counts.values())
    return counts


def subscribe_email(
    *,
    email: str,
    full_name: str | None = None,
) -> tuple[Subscriber, str]:
    """
    Start or resume subscription (PENDING until verified).

    Returns (subscriber, outcome):
    created | pending_resent | already_active | unsubscribed_resent | mail_failed
    """
    publication = get_or_create_default_publication()
    email = _normalize_email(email)
    name = (full_name or "").strip() or None
    existing = find_by_email(email, publication.id)

    if existing is not None and existing.status == SubscriberStatus.ACTIVE:
        return existing, "already_active"

    token = _new_verification_token()

    if existing is not None:
        was_unsubscribed = existing.status == SubscriberStatus.UNSUBSCRIBED
        existing.full_name = name or existing.full_name
        existing.status = SubscriberStatus.PENDING
        existing.verification_token = token
        existing.unsubscribed_at = None
        outcome = "unsubscribed_resent" if was_unsubscribed else "pending_resent"
        log_activity("subscriber.verification_sent", f"Verification sent to {email}")
        db.session.commit()
        mail_error = _try_send_verification(email, token)
        if mail_error:
            return existing, "mail_failed"
        return existing, outcome

    subscriber = Subscriber(
        publication_id=publication.id,
        email=email,
        full_name=name,
        status=SubscriberStatus.PENDING,
        verification_token=token,
        subscribed_at=None,
    )
    db.session.add(subscriber)
    log_activity("subscriber.created", f"Pending subscriber {email}")
    db.session.commit()
    mail_error = _try_send_verification(email, token)
    if mail_error:
        return subscriber, "mail_failed"
    return subscriber, "created"


def _try_send_verification(email: str, token: str) -> str | None:
    """Send confirmation mail. Returns None on success, or an error message."""
    try:
        send_subscription_verification_email(email, token)
        return None
    except (MailSendError, MailNotConfiguredError) as exc:
        from flask import current_app

        current_app.logger.error(
            "Subscription verification email failed for %s: %s",
            email,
            exc,
        )
        log_activity(
            "subscriber.verification_failed",
            f"Could not email {email}: {exc}",
        )
        return str(exc)


def verify_subscription(token: str) -> Subscriber | None:
    if not token:
        return None
    subscriber = db.session.scalar(
        select(Subscriber).where(Subscriber.verification_token == token)
    )
    if subscriber is None:
        return None
    subscriber.status = SubscriberStatus.ACTIVE
    subscriber.verification_token = None
    subscriber.subscribed_at = _now()
    subscriber.unsubscribed_at = None
    log_activity("subscriber.verified", f"Verified {subscriber.email}")
    db.session.commit()
    return subscriber


def unsubscribe_by_token(token: str) -> Subscriber | None:
    payload = verify_unsubscribe_token(token)
    if payload is None:
        return None
    try:
        publication_id = uuid.UUID(str(payload["publication_id"]))
    except (TypeError, ValueError):
        return None
    subscriber = find_by_email(payload["email"], publication_id)
    if subscriber is None:
        return None
    return _mark_unsubscribed(subscriber)


def unsubscribe_by_email(email: str) -> Subscriber | None:
    subscriber = find_by_email(email)
    if subscriber is None:
        return None
    return _mark_unsubscribed(subscriber)


def _mark_unsubscribed(subscriber: Subscriber) -> Subscriber:
    if subscriber.status == SubscriberStatus.UNSUBSCRIBED:
        return subscriber
    subscriber.status = SubscriberStatus.UNSUBSCRIBED
    subscriber.unsubscribed_at = _now()
    subscriber.verification_token = None
    log_activity("subscriber.unsubscribed", f"Unsubscribed {subscriber.email}")
    db.session.commit()
    try:
        send_unsubscribe_confirmation_email(subscriber.email)
    except (MailSendError, MailNotConfiguredError) as exc:
        log_activity(
            "subscriber.unsubscribe_email_failed",
            f"Unsubscribed {subscriber.email} but confirmation email failed: {exc}",
        )
    return subscriber


def unsubscribe_link_for(subscriber: Subscriber) -> str:
    from flask import url_for

    token = generate_unsubscribe_token(
        subscriber.email,
        str(subscriber.publication_id),
    )
    return url_for("main.unsubscribe", token=token, _external=True)


def resend_verification(subscriber: Subscriber) -> None:
    if subscriber.status == SubscriberStatus.ACTIVE:
        raise SubscriberError("Subscriber is already active.")
    token = _new_verification_token()
    subscriber.status = SubscriberStatus.PENDING
    subscriber.verification_token = token
    log_activity(
        "subscriber.verification_resent",
        f"Resent verification to {subscriber.email}",
    )
    db.session.commit()
    mail_error = _try_send_verification(subscriber.email, token)
    if mail_error:
        raise SubscriberError(
            f"Confirmation email could not be sent: {mail_error}"
        )


def resend_all_pending(
    *,
    delay_seconds: float = 0.4,
    limit: int = 150,
) -> dict[str, int | list[str]]:
    """Resend confirmation emails to PENDING subscribers (batched)."""
    pending = list_subscribers(status=SubscriberStatus.PENDING.value)
    total = len(pending)
    batch = pending[: max(limit, 0)]
    stats: dict[str, int | list[str]] = {
        "total_pending": total,
        "attempted": len(batch),
        "sent": 0,
        "failed": 0,
        "remaining": max(total - len(batch), 0),
        "errors": [],
    }
    for index, subscriber in enumerate(batch):
        try:
            resend_verification(subscriber)
            stats["sent"] = int(stats["sent"]) + 1
        except SubscriberError as exc:
            stats["failed"] = int(stats["failed"]) + 1
            errors = stats["errors"]
            assert isinstance(errors, list)
            if len(errors) < 10:
                errors.append(f"{subscriber.email}: {exc}")
        if delay_seconds > 0 and index < len(batch) - 1:
            time.sleep(delay_seconds)
    log_activity(
        "subscriber.verification_bulk_resent",
        (
            f"Bulk resend pending: sent={stats['sent']} failed={stats['failed']} "
            f"attempted={stats['attempted']} remaining={stats['remaining']}"
        ),
    )
    return stats


def set_status(subscriber: Subscriber, status: SubscriberStatus) -> Subscriber:
    subscriber.status = status
    if status == SubscriberStatus.ACTIVE:
        subscriber.subscribed_at = subscriber.subscribed_at or _now()
        subscriber.unsubscribed_at = None
        subscriber.verification_token = None
    elif status == SubscriberStatus.UNSUBSCRIBED:
        subscriber.unsubscribed_at = subscriber.unsubscribed_at or _now()
        subscriber.verification_token = None
    elif status == SubscriberStatus.PENDING:
        if not subscriber.verification_token:
            subscriber.verification_token = _new_verification_token()
    log_activity("subscriber.status_changed", f"{subscriber.email} → {status.value}")
    db.session.commit()
    return subscriber


def create_subscriber_admin(
    *,
    email: str,
    full_name: str | None,
    status: SubscriberStatus,
) -> Subscriber:
    publication = get_or_create_default_publication()
    email = _normalize_email(email)
    if find_by_email(email, publication.id) is not None:
        raise SubscriberError("A subscriber with that email already exists.")

    subscriber = Subscriber(
        publication_id=publication.id,
        email=email,
        full_name=(full_name or "").strip() or None,
        status=status,
        subscribed_at=_now() if status == SubscriberStatus.ACTIVE else None,
        unsubscribed_at=_now() if status == SubscriberStatus.UNSUBSCRIBED else None,
        verification_token=(
            _new_verification_token() if status == SubscriberStatus.PENDING else None
        ),
    )
    db.session.add(subscriber)
    log_activity("subscriber.created_admin", f"Admin created {email} ({status.value})")
    db.session.commit()
    return subscriber


def update_subscriber_admin(
    subscriber: Subscriber,
    *,
    email: str,
    full_name: str | None,
    status: SubscriberStatus,
) -> Subscriber:
    email = _normalize_email(email)
    other = find_by_email(email, subscriber.publication_id)
    if other is not None and other.id != subscriber.id:
        raise SubscriberError("A subscriber with that email already exists.")

    subscriber.email = email
    subscriber.full_name = (full_name or "").strip() or None
    return set_status(subscriber, status)


def delete_subscriber(subscriber: Subscriber) -> None:
    email = subscriber.email
    log_activity("subscriber.deleted", f"Deleted subscriber {email}")
    db.session.delete(subscriber)
    db.session.commit()


def export_csv(subscribers: list[Subscriber] | None = None) -> str:
    rows = subscribers if subscribers is not None else list_subscribers()
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["email", "full_name", "status", "subscribed_at", "unsubscribed_at"],
    )
    writer.writeheader()
    for item in rows:
        writer.writerow(
            {
                "email": item.email,
                "full_name": item.full_name or "",
                "status": item.status.value,
                "subscribed_at": item.subscribed_at.isoformat() if item.subscribed_at else "",
                "unsubscribed_at": (
                    item.unsubscribed_at.isoformat() if item.unsubscribed_at else ""
                ),
            }
        )
    return buffer.getvalue()


def import_csv(file_storage) -> dict[str, int]:
    """Import CSV with columns: email (required), full_name, status."""
    publication = get_or_create_default_publication()
    raw = file_storage.read()
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else str(raw)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise SubscriberError("CSV is empty or missing a header row.")

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    if "email" not in headers:
        raise SubscriberError("CSV must include an 'email' column.")

    stats = {"created": 0, "updated": 0, "skipped": 0}
    for row in reader:
        email_raw = (row.get(headers["email"]) or "").strip()
        if not email_raw or "@" not in email_raw:
            stats["skipped"] += 1
            continue

        email = _normalize_email(email_raw)
        name_header = headers.get("full_name") or headers.get("name")
        name = (row.get(name_header) or "").strip() if name_header else ""
        status_header = headers.get("status")
        status_value = (
            (row.get(status_header) or "PENDING").strip().upper()
            if status_header
            else "PENDING"
        )
        try:
            status = SubscriberStatus(status_value)
        except ValueError:
            status = SubscriberStatus.PENDING

        existing = find_by_email(email, publication.id)
        if existing is None:
            db.session.add(
                Subscriber(
                    publication_id=publication.id,
                    email=email,
                    full_name=name or None,
                    status=status,
                    subscribed_at=_now() if status == SubscriberStatus.ACTIVE else None,
                    unsubscribed_at=(
                        _now() if status == SubscriberStatus.UNSUBSCRIBED else None
                    ),
                    verification_token=(
                        _new_verification_token()
                        if status == SubscriberStatus.PENDING
                        else None
                    ),
                )
            )
            stats["created"] += 1
        else:
            existing.full_name = name or existing.full_name
            existing.status = status
            if status == SubscriberStatus.ACTIVE:
                existing.subscribed_at = existing.subscribed_at or _now()
                existing.unsubscribed_at = None
                existing.verification_token = None
            elif status == SubscriberStatus.UNSUBSCRIBED:
                existing.unsubscribed_at = existing.unsubscribed_at or _now()
                existing.verification_token = None
            elif status == SubscriberStatus.PENDING and not existing.verification_token:
                existing.verification_token = _new_verification_token()
            stats["updated"] += 1

    log_activity(
        "subscriber.imported",
        f"CSV import created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}",
    )
    db.session.commit()
    return stats
