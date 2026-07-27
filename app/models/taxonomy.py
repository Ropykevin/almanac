"""Categories and tags (publication-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.publication import Publication


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("publication_id", "slug", name="uq_categories_publication_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    publication: Mapped["Publication"] = relationship("Publication", back_populates="categories")
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        secondary="article_categories",
        back_populates="categories",
    )

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class Tag(db.Model):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("publication_id", "slug", name="uq_tags_publication_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    publication: Mapped["Publication"] = relationship("Publication", back_populates="tags")
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        secondary="article_tags",
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.slug}>"
