"""Authorization decorators for role-protected routes."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from flask import abort, flash, redirect, url_for
from flask_login import current_user

from app.models.enums import UserRole

F = TypeVar("F", bound=Callable[..., Any])


def role_required(*roles: UserRole | str) -> Callable[[F], F]:
    """Require login and one of the given roles."""

    def decorator(view: F) -> F:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            if not current_user.is_active:
                flash("Your account is inactive.", "error")
                return redirect(url_for("auth.login"))
            if not current_user.has_role(*roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator


def admin_required(view: F) -> F:
    """Allow Admin or Super Admin."""
    return role_required(UserRole.ADMIN, UserRole.SUPER_ADMIN)(view)


def super_admin_required(view: F) -> F:
    """Allow Super Admin only."""
    return role_required(UserRole.SUPER_ADMIN)(view)


def staff_required(view: F) -> F:
    """Allow any staff role (Editor, Admin, Super Admin)."""
    return role_required(UserRole.EDITOR, UserRole.ADMIN, UserRole.SUPER_ADMIN)(view)
