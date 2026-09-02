"""Subscribers, newsletters, and deliveries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, pg_enum, uuid_pk
from app.models.enums import DeliveryStatus, NewsletterStatus, SubscriberStatus

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.publication import Publication


class Subscriber(db.Model):
    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("publication_id", "email", name="uq_subscribers_publication_email"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    verification_token: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[SubscriberStatus] = mapped_column(
        pg_enum(SubscriberStatus, "subscriber_status"),
        nullable=False,
        default=SubscriberStatus.PENDING,
        server_default=SubscriberStatus.PENDING.value,
    )
    subscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    publication: Mapped["Publication"] = relationship(
        "Publication",
        back_populates="subscribers",
    )
    deliveries: Mapped[list["NewsletterDelivery"]] = relationship(
        "NewsletterDelivery",
        back_populates="subscriber",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subscriber {self.email}>"


class Newsletter(db.Model):
    __tablename__ = "newsletters"

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_content: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[NewsletterStatus] = mapped_column(
        pg_enum(NewsletterStatus, "newsletter_status"),
        nullable=False,
        default=NewsletterStatus.DRAFT,
        server_default=NewsletterStatus.DRAFT.value,
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    publication: Mapped["Publication"] = relationship(
        "Publication",
        back_populates="newsletters",
    )
    article: Mapped[Optional["Article"]] = relationship(
        "Article",
        back_populates="newsletters",
    )
    deliveries: Mapped[list["NewsletterDelivery"]] = relationship(
        "NewsletterDelivery",
        back_populates="newsletter",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Newsletter {self.subject!r} ({self.status})>"


class NewsletterDelivery(db.Model):
    __tablename__ = "newsletter_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "newsletter_id",
            "subscriber_id",
            name="uq_newsletter_deliveries_recipient",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    newsletter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("newsletters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscriber_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("subscribers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        pg_enum(DeliveryStatus, "delivery_status"),
        nullable=False,
        default=DeliveryStatus.PENDING,
        server_default=DeliveryStatus.PENDING.value,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    newsletter: Mapped["Newsletter"] = relationship(
        "Newsletter",
        back_populates="deliveries",
    )
    subscriber: Mapped["Subscriber"] = relationship(
        "Subscriber",
        back_populates="deliveries",
    )

    def __repr__(self) -> str:
        return f"<NewsletterDelivery {self.newsletter_id}→{self.subscriber_id}>"
