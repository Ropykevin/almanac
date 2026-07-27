"""Media assets."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.publication import Publication
    from app.models.user import User


class Media(db.Model):
    __tablename__ = "media"

    id: Mapped[uuid.UUID] = uuid_pk()
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    uploader: Mapped["User"] = relationship(
        "User",
        back_populates="media_uploads",
        foreign_keys=[uploaded_by],
    )
    publication_logos: Mapped[list["Publication"]] = relationship(
        "Publication",
        back_populates="logo",
        foreign_keys="Publication.logo_id",
    )
    publication_banners: Mapped[list["Publication"]] = relationship(
        "Publication",
        back_populates="banner",
        foreign_keys="Publication.banner_id",
    )
    featured_in_articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="featured_image_media",
        foreign_keys="Article.featured_image",
    )

    def __repr__(self) -> str:
        return f"<Media {self.file_name}>"
