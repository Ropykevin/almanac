"""Staff user management (Super Admin)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import PublicationUser, User
from app.models.enums import UserRole
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity


class UserAdminError(ValueError):
    """Invalid user admin action."""


def list_users(
    *,
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        try:
            stmt = stmt.where(User.role == UserRole(role.upper()))
        except ValueError:
            pass
    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(User.is_active.is_(False))
    query = (q or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(pattern), User.email.ilike(pattern))
        )
    return list(db.session.scalars(stmt).all())


def count_users() -> dict[str, int]:
    total = db.session.scalar(select(func.count()).select_from(User)) or 0
    active = (
        db.session.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
        or 0
    )
    by_role = {
        row[0].value: int(row[1])
        for row in db.session.execute(
            select(User.role, func.count()).group_by(User.role)
        ).all()
    }
    return {
        "ALL": int(total),
        "active": int(active),
        "inactive": int(total) - int(active),
        "SUPER_ADMIN": by_role.get("SUPER_ADMIN", 0),
        "ADMIN": by_role.get("ADMIN", 0),
        "EDITOR": by_role.get("EDITOR", 0),
    }


def get_user(user_id: uuid.UUID) -> User | None:
    return db.session.scalar(select(User).where(User.id == user_id))


def _count_active_super_admins() -> int:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.SUPER_ADMIN,
                User.is_active.is_(True),
            )
        )
        or 0
    )


def _ensure_not_last_super_admin(user: User, *, demoting: bool, deactivating: bool) -> None:
    if user.role != UserRole.SUPER_ADMIN or not user.is_active:
        return
    if not demoting and not deactivating:
        return
    if _count_active_super_admins() <= 1:
        raise UserAdminError(
            "Cannot remove or deactivate the last active Super Admin."
        )


def create_user(
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole | str,
    bio: str | None = None,
    is_active: bool = True,
) -> User:
    name = (full_name or "").strip()
    mail = (email or "").strip().lower()
    if not name:
        raise UserAdminError("Full name is required.")
    if not mail:
        raise UserAdminError("Email is required.")
    if len(password or "") < 8:
        raise UserAdminError("Password must be at least 8 characters.")

    try:
        role_value = role if isinstance(role, UserRole) else UserRole(str(role).upper())
    except ValueError as exc:
        raise UserAdminError("Invalid role.") from exc

    existing = db.session.scalar(select(User).where(User.email == mail))
    if existing is not None:
        raise UserAdminError(f"A user with email {mail} already exists.")

    user = User(
        full_name=name[:150],
        email=mail[:150],
        role=role_value,
        bio=(bio or "").strip() or None,
        is_active=bool(is_active),
        email_verified=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    publication = get_or_create_default_publication()
    membership = db.session.scalar(
        select(PublicationUser).where(
            PublicationUser.publication_id == publication.id,
            PublicationUser.user_id == user.id,
        )
    )
    if membership is None:
        db.session.add(
            PublicationUser(
                publication_id=publication.id,
                user_id=user.id,
                role=role_value.value,
            )
        )

    log_activity("user.created", f"Created {user.role_label}: {user.email}")
    db.session.commit()
    return user


def update_user(
    user: User,
    *,
    actor: User,
    full_name: str,
    email: str,
    role: UserRole | str,
    bio: str | None = None,
    is_active: bool = True,
    password: str | None = None,
) -> User:
    name = (full_name or "").strip()
    mail = (email or "").strip().lower()
    if not name:
        raise UserAdminError("Full name is required.")
    if not mail:
        raise UserAdminError("Email is required.")

    try:
        role_value = role if isinstance(role, UserRole) else UserRole(str(role).upper())
    except ValueError as exc:
        raise UserAdminError("Invalid role.") from exc

    duplicate = db.session.scalar(
        select(User).where(User.email == mail, User.id != user.id)
    )
    if duplicate is not None:
        raise UserAdminError(f"A user with email {mail} already exists.")

    demoting = user.role == UserRole.SUPER_ADMIN and role_value != UserRole.SUPER_ADMIN
    deactivating = user.is_active and not is_active
    _ensure_not_last_super_admin(user, demoting=demoting, deactivating=deactivating)

    if actor.id == user.id and demoting:
        raise UserAdminError("You cannot demote your own Super Admin role.")
    if actor.id == user.id and deactivating:
        raise UserAdminError("You cannot deactivate your own account.")

    if password:
        if len(password) < 8:
            raise UserAdminError("Password must be at least 8 characters.")
        user.set_password(password)

    user.full_name = name[:150]
    user.email = mail[:150]
    user.role = role_value
    user.bio = (bio or "").strip() or None
    user.is_active = bool(is_active)

    # Keep publication membership role in sync when present
    membership = db.session.scalar(
        select(PublicationUser).where(PublicationUser.user_id == user.id)
    )
    if membership is not None:
        membership.role = role_value.value

    log_activity("user.updated", f"Updated {user.role_label}: {user.email}")
    db.session.commit()
    return user


def set_user_active(user: User, *, actor: User, active: bool) -> User:
    if actor.id == user.id and not active:
        raise UserAdminError("You cannot deactivate your own account.")
    if user.is_active and not active:
        _ensure_not_last_super_admin(user, demoting=False, deactivating=True)
    user.is_active = bool(active)
    log_activity(
        "user.activated" if active else "user.deactivated",
        f"{'Activated' if active else 'Deactivated'} {user.email}",
    )
    db.session.commit()
    return user
