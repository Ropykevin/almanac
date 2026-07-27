"""Publication key/value settings."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.publication import Publication


class Setting(db.Model):
    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("publication_id", "setting_key", name="uq_settings_publication_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    setting_key: Mapped[str] = mapped_column(String(150), nullable=False)
    setting_value: Mapped[Optional[str]] = mapped_column(Text)

    publication: Mapped["Publication"] = relationship("Publication", back_populates="settings")

    def __repr__(self) -> str:
        return f"<Setting {self.setting_key}>"
