"""Articles and related tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, pg_enum, updated_at_col, utcnow, uuid_pk
from app.models.enums import ArticleStatus

if TYPE_CHECKING:
    from app.models.media import Media
    from app.models.newsletter import Newsletter
    from app.models.publication import Publication
    from app.models.taxonomy import Category, Tag
    from app.models.user import User


class Article(db.Model):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("publication_id", "slug", name="uq_articles_publication_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(Text)
    excerpt: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    featured_image: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("media.id", ondelete="SET NULL"),
        nullable=True,
    )
    reading_time: Mapped[Optional[int]] = mapped_column(Integer)
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_comments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[ArticleStatus] = mapped_column(
        pg_enum(ArticleStatus, "article_status"),
        nullable=False,
        default=ArticleStatus.DRAFT,
        server_default=ArticleStatus.DRAFT.value,
        index=True,
    )
    seo_title: Mapped[Optional[str]] = mapped_column(String(255))
    seo_description: Mapped[Optional[str]] = mapped_column(Text)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    publication: Mapped["Publication"] = relationship("Publication", back_populates="articles")
    author: Mapped["User"] = relationship(
        "User",
        back_populates="articles",
        foreign_keys=[author_id],
    )
    featured_image_media: Mapped[Optional["Media"]] = relationship(
        "Media",
        back_populates="featured_in_articles",
        foreign_keys=[featured_image],
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="article_tags",
        back_populates="articles",
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        secondary="article_categories",
        back_populates="articles",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    likes: Mapped[list["ArticleLike"]] = relationship(
        "ArticleLike",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    views: Mapped[list["ArticleView"]] = relationship(
        "ArticleView",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["ArticleRevision"]] = relationship(
        "ArticleRevision",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    newsletters: Mapped[list["Newsletter"]] = relationship(
        "Newsletter",
        back_populates="article",
    )

    def __repr__(self) -> str:
        return f"<Article {self.slug} ({self.status})>"


class ArticleTag(db.Model):
    __tablename__ = "article_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArticleCategory(db.Model):
    __tablename__ = "article_categories"

    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Comment(db.Model):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    created_at: Mapped[datetime] = created_at_col()

    article: Mapped["Article"] = relationship("Article", back_populates="comments")

    def __repr__(self) -> str:
        return f"<Comment {self.id}>"


class ArticleLike(db.Model):
    __tablename__ = "article_likes"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "visitor_key",
            name="uq_article_likes_article_visitor",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    article: Mapped["Article"] = relationship("Article", back_populates="likes")

    def __repr__(self) -> str:
        return f"<ArticleLike {self.id}>"


class ArticleView(db.Model):
    __tablename__ = "article_views"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    browser: Mapped[Optional[str]] = mapped_column(String(100))
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )

    article: Mapped["Article"] = relationship("Article", back_populates="views")


class ArticleRevision(db.Model):
    __tablename__ = "article_revisions"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "revision_number",
            name="uq_article_revisions_number",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    editor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    article: Mapped["Article"] = relationship("Article", back_populates="revisions")
    editor: Mapped["User"] = relationship("User", back_populates="revisions")

    def __repr__(self) -> str:
        return f"<ArticleRevision {self.article_id}#{self.revision_number}>"
