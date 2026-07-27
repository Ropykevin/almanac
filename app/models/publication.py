"""Publications and membership."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, updated_at_col, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.media import Media
    from app.models.newsletter import Newsletter, Subscriber
    from app.models.settings import Setting
    from app.models.taxonomy import Category, Tag
    from app.models.user import User


class Publication(db.Model):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    logo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("media.id", ondelete="SET NULL", use_alter=True, name="fk_publications_logo_id"),
        nullable=True,
    )
    banner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey(
            "media.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_publications_banner_id",
        ),
        nullable=True,
    )
    primary_color: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    logo: Mapped[Optional["Media"]] = relationship(
        "Media",
        foreign_keys=[logo_id],
        back_populates="publication_logos",
        post_update=True,
    )
    banner: Mapped[Optional["Media"]] = relationship(
        "Media",
        foreign_keys=[banner_id],
        back_populates="publication_banners",
        post_update=True,
    )
    members: Mapped[list["PublicationUser"]] = relationship(
        "PublicationUser",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    subscribers: Mapped[list["Subscriber"]] = relationship(
        "Subscriber",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    newsletters: Mapped[list["Newsletter"]] = relationship(
        "Newsletter",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    settings: Mapped[list["Setting"]] = relationship(
        "Setting",
        back_populates="publication",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Publication {self.slug}>"


class PublicationUser(db.Model):
    """Publication-scoped membership (role is a free-form varchar per schema)."""

    __tablename__ = "publication_users"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    publication: Mapped["Publication"] = relationship("Publication", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="publication_memberships")

    def __repr__(self) -> str:
        return f"<PublicationUser pub={self.publication_id} user={self.user_id}>"
