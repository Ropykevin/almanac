"""Research projects shown on the public site."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, pg_enum, updated_at_col, uuid_pk
from app.models.enums import ProjectStatus

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.media import Media
    from app.models.publication import Publication


class Project(db.Model):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("publication_id", "slug", name="uq_projects_publication_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        pg_enum(ProjectStatus, "project_status"),
        nullable=False,
        default=ProjectStatus.LIVE,
        server_default=ProjectStatus.LIVE.value,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    publication: Mapped["Publication"] = relationship("Publication")
    documents: Mapped[list["ProjectDocument"]] = relationship(
        "ProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectDocument.sort_order",
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="project",
        foreign_keys="Article.project_id",
    )

    @property
    def status_label(self) -> str:
        if self.status == ProjectStatus.COMING_SOON:
            return "Coming soon"
        return "Live"

    def __repr__(self) -> str:
        return f"<Project {self.title!r}>"


class ProjectDocument(db.Model):
    """A downloadable file attached to a research project."""

    __tablename__ = "project_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("media.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = created_at_col()

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    media: Mapped["Media"] = relationship("Media")

    @property
    def display_title(self) -> str:
        if self.title and self.title.strip():
            return self.title.strip()
        if self.media is not None and self.media.original_name:
            return self.media.original_name
        return "Document"

    def __repr__(self) -> str:
        return f"<ProjectDocument {self.display_title!r}>"
