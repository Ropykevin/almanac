"""PostgreSQL enum types from the approved Liminal schema."""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"


class ArticleStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SubscriberStatus(enum.StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    BOUNCED = "BOUNCED"


class NewsletterStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"
    SENT = "SENT"


class DeliveryStatus(enum.StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    OPENED = "OPENED"
    CLICKED = "CLICKED"
    FAILED = "FAILED"


class ProjectStatus(enum.StrEnum):
    LIVE = "LIVE"
    COMING_SOON = "COMING_SOON"


ROLE_RANK: dict[UserRole, int] = {
    UserRole.EDITOR: 1,
    UserRole.ADMIN: 2,
    UserRole.SUPER_ADMIN: 3,
}
