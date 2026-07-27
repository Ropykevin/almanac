"""Admin subscriber management routes."""

from __future__ import annotations

import uuid

from flask import (
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.subscribers import SubscriberAdminForm, SubscriberImportForm
from app.models.enums import SubscriberStatus
from app.services import subscribers as subscriber_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


@admin_bp.route("/subscribers")
@login_required
@staff_required
def subscriber_list():
    status = (request.args.get("status") or "ALL").upper()
    q = (request.args.get("q") or "").strip() or None
    filter_status = None if status in ("", "ALL") else status
    items = subscriber_service.list_subscribers(status=filter_status, q=q)
    counts = subscriber_service.count_by_status()
    return render_template(
        "admin/subscribers/list.html",
        subscribers=items,
        counts=counts,
        current_status=status if status else "ALL",
        q=q or "",
        breadcrumbs=[{"label": "Subscribers", "url": None}],
        page_title="Subscribers",
        active_nav="subscribers",
    )


@admin_bp.route("/subscribers/new", methods=["GET", "POST"])
@login_required
@staff_required
def subscriber_create():
    form = SubscriberAdminForm()
    if form.validate_on_submit():
        try:
            subscriber = subscriber_service.create_subscriber_admin(
                email=form.email.data,
                full_name=form.full_name.data,
                status=SubscriberStatus(form.status.data),
            )
        except subscriber_service.SubscriberError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Subscriber “{subscriber.email}” created.", "success")
            return redirect(url_for("admin.subscriber_list"))
    return render_template(
        "admin/subscribers/form.html",
        form=form,
        subscriber=None,
        breadcrumbs=[
            {"label": "Subscribers", "url": url_for("admin.subscriber_list")},
            {"label": "New", "url": None},
        ],
        page_title="New subscriber",
        active_nav="subscribers",
    )


@admin_bp.route("/subscribers/<subscriber_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def subscriber_edit(subscriber_id: str):
    subscriber = subscriber_service.get_subscriber(_parse_uuid(subscriber_id))
    if subscriber is None:
        abort(404)

    form = SubscriberAdminForm()
    if request.method == "GET":
        form.full_name.data = subscriber.full_name
        form.email.data = subscriber.email
        form.status.data = subscriber.status.value

    if form.validate_on_submit():
        try:
            subscriber = subscriber_service.update_subscriber_admin(
                subscriber,
                email=form.email.data,
                full_name=form.full_name.data,
                status=SubscriberStatus(form.status.data),
            )
        except subscriber_service.SubscriberError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Subscriber “{subscriber.email}” saved.", "success")
            return redirect(url_for("admin.subscriber_list"))

    return render_template(
        "admin/subscribers/form.html",
        form=form,
        subscriber=subscriber,
        breadcrumbs=[
            {"label": "Subscribers", "url": url_for("admin.subscriber_list")},
            {"label": subscriber.email, "url": None},
        ],
        page_title="Edit subscriber",
        active_nav="subscribers",
    )


@admin_bp.route("/subscribers/<subscriber_id>/resend", methods=["POST"])
@login_required
@staff_required
def subscriber_resend(subscriber_id: str):
    subscriber = subscriber_service.get_subscriber(_parse_uuid(subscriber_id))
    if subscriber is None:
        abort(404)
    try:
        subscriber_service.resend_verification(subscriber)
    except subscriber_service.SubscriberError as exc:
        flash(str(exc), "error")
    else:
        flash(f"Verification email sent to {subscriber.email}.", "success")
    return redirect(url_for("admin.subscriber_list"))


@admin_bp.route("/subscribers/<subscriber_id>/delete", methods=["POST"])
@login_required
@staff_required
def subscriber_delete(subscriber_id: str):
    subscriber = subscriber_service.get_subscriber(_parse_uuid(subscriber_id))
    if subscriber is None:
        abort(404)
    email = subscriber.email
    subscriber_service.delete_subscriber(subscriber)
    flash(f"Subscriber “{email}” deleted.", "info")
    return redirect(url_for("admin.subscriber_list"))


@admin_bp.route("/subscribers/export")
@login_required
@staff_required
def subscriber_export():
    status = (request.args.get("status") or "ALL").upper()
    q = (request.args.get("q") or "").strip() or None
    filter_status = None if status in ("", "ALL") else status
    items = subscriber_service.list_subscribers(status=filter_status, q=q)
    csv_body = subscriber_service.export_csv(items)
    return Response(
        csv_body,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=subscribers.csv",
        },
    )


@admin_bp.route("/subscribers/import", methods=["GET", "POST"])
@login_required
@staff_required
def subscriber_import():
    form = SubscriberImportForm()
    if form.validate_on_submit():
        try:
            stats = subscriber_service.import_csv(form.file.data)
        except subscriber_service.SubscriberError as exc:
            flash(str(exc), "error")
        except UnicodeDecodeError:
            flash("Could not read the CSV file. Use UTF-8 encoding.", "error")
        else:
            flash(
                f"Import complete: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['skipped']} skipped.",
                "success",
            )
            return redirect(url_for("admin.subscriber_list"))
    return render_template(
        "admin/subscribers/import.html",
        form=form,
        breadcrumbs=[
            {"label": "Subscribers", "url": url_for("admin.subscriber_list")},
            {"label": "Import", "url": None},
        ],
        page_title="Import subscribers",
        active_nav="subscribers",
    )
