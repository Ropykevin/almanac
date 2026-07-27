"""Super Admin staff user management."""

from __future__ import annotations

import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.decorators import super_admin_required
from app.forms.users import UserCreateForm, UserEditForm
from app.services import users as user_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


@admin_bp.route("/users")
@login_required
@super_admin_required
def user_list():
    role = (request.args.get("role") or "ALL").upper()
    status = (request.args.get("status") or "ALL").lower()
    q = (request.args.get("q") or "").strip() or None
    filter_role = None if role in ("", "ALL") else role
    filter_status = None if status in ("", "all") else status
    items = user_service.list_users(role=filter_role, status=filter_status, q=q)
    counts = user_service.count_users()
    return render_template(
        "admin/users/list.html",
        users=items,
        counts=counts,
        current_role=role if role else "ALL",
        current_status=status if status else "all",
        q=q or "",
        breadcrumbs=[{"label": "Users", "url": None}],
        page_title="Users",
        active_nav="users",
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def user_create():
    form = UserCreateForm()
    if form.validate_on_submit():
        try:
            user = user_service.create_user(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data,
                role=form.role.data,
                bio=form.bio.data,
                is_active=bool(form.is_active.data),
            )
        except user_service.UserAdminError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Created {user.role_label}: {user.email}", "success")
            return redirect(url_for("admin.user_list"))
    return render_template(
        "admin/users/form.html",
        form=form,
        user=None,
        breadcrumbs=[
            {"label": "Users", "url": url_for("admin.user_list")},
            {"label": "New", "url": None},
        ],
        page_title="New user",
        active_nav="users",
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def user_edit(user_id: str):
    user = user_service.get_user(_parse_uuid(user_id))
    if user is None:
        abort(404)

    form = UserEditForm()
    if request.method == "GET":
        form.full_name.data = user.full_name
        form.email.data = user.email
        form.role.data = user.role.value
        form.bio.data = user.bio or ""
        form.is_active.data = user.is_active

    if form.validate_on_submit():
        try:
            user = user_service.update_user(
                user,
                actor=current_user,
                full_name=form.full_name.data,
                email=form.email.data,
                role=form.role.data,
                bio=form.bio.data,
                is_active=bool(form.is_active.data),
                password=form.password.data or None,
            )
        except user_service.UserAdminError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Updated {user.email}.", "success")
            return redirect(url_for("admin.user_list"))

    return render_template(
        "admin/users/form.html",
        form=form,
        user=user,
        breadcrumbs=[
            {"label": "Users", "url": url_for("admin.user_list")},
            {"label": user.full_name, "url": None},
        ],
        page_title=f"Edit {user.full_name}",
        active_nav="users",
    )


@admin_bp.route("/users/<user_id>/deactivate", methods=["POST"])
@login_required
@super_admin_required
def user_deactivate(user_id: str):
    user = user_service.get_user(_parse_uuid(user_id))
    if user is None:
        abort(404)
    try:
        user_service.set_user_active(user, actor=current_user, active=False)
    except user_service.UserAdminError as exc:
        flash(str(exc), "error")
    else:
        flash(f"Deactivated {user.email}.", "success")
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/users/<user_id>/activate", methods=["POST"])
@login_required
@super_admin_required
def user_activate(user_id: str):
    user = user_service.get_user(_parse_uuid(user_id))
    if user is None:
        abort(404)
    try:
        user_service.set_user_active(user, actor=current_user, active=True)
    except user_service.UserAdminError as exc:
        flash(str(exc), "error")
    else:
        flash(f"Activated {user.email}.", "success")
    return redirect(request.referrer or url_for("admin.user_list"))
