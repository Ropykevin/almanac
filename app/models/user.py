"""User model (aligned with approved DBML schema)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import created_at_col, pg_enum, updated_at_col, utcnow, uuid_pk
from app.models.enums import ROLE_RANK, UserRole

if TYPE_CHECKING:
    from app.models.activity import ActivityLog
    from app.models.article import Article, ArticleRevision
    from app.models.media import Media
    from app.models.publication import PublicationUser


class User(UserMixin, db.Model):
    """Platform user — Super Admin, Admin, or Editor."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"),
        nullable=False,
        default=UserRole.EDITOR,
        server_default=UserRole.EDITOR.value,
    )
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("media.id", ondelete="SET NULL", use_alter=True, name="fk_users_avatar_id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    avatar: Mapped[Optional["Media"]] = relationship(
        "Media",
        foreign_keys=[avatar_id],
        post_update=True,
    )
    media_uploads: Mapped[list["Media"]] = relationship(
        "Media",
        back_populates="uploader",
        foreign_keys="Media.uploaded_by",
    )
    publication_memberships: Mapped[list["PublicationUser"]] = relationship(
        "PublicationUser",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="author",
        foreign_keys="Article.author_id",
    )
    revisions: Mapped[list["ArticleRevision"]] = relationship(
        "ArticleRevision",
        back_populates="editor",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="user",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles: UserRole | str) -> bool:
        wanted = set()
        for role in roles:
            if isinstance(role, UserRole):
                wanted.add(role)
            else:
                wanted.add(UserRole(str(role).upper()))
        return self.role in wanted

    def has_at_least(self, minimum: UserRole | str) -> bool:
        min_role = (
            minimum if isinstance(minimum, UserRole) else UserRole(str(minimum).upper())
        )
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK.get(min_role, 0)

    def touch_login(self) -> None:
        self.last_login = utcnow()

    @property
    def role_label(self) -> str:
        labels = {
            UserRole.SUPER_ADMIN: "Super Admin",
            UserRole.ADMIN: "Admin",
            UserRole.EDITOR: "Editor",
        }
        return labels.get(self.role, self.role.value)

    @property
    def public_role_label(self) -> str:
        """Reader-facing title — never exposes internal admin roles."""
        return "Editor"

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
