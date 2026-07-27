"""Activity log helpers."""

from __future__ import annotations

import uuid

from flask import request
from flask_login import current_user

from app.extensions import db
from app.models import ActivityLog


def log_activity(action: str, description: str | None = None) -> None:
    """Persist an activity log row for the current request/user."""
    user_id = None
    if current_user and getattr(current_user, "is_authenticated", False):
        user_id = getattr(current_user, "id", None)
        if isinstance(user_id, uuid.UUID) or user_id is None:
            pass
        else:
            try:
                user_id = uuid.UUID(str(user_id))
            except (TypeError, ValueError):
                user_id = None

    entry = ActivityLog(
        user_id=user_id,
        action=action,
        description=description,
        ip_address=(request.remote_addr if request else None),
    )
    db.session.add(entry)
