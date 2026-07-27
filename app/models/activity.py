"""Activity audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at_col()

    user: Mapped[Optional["User"]] = relationship("User", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action}>"
