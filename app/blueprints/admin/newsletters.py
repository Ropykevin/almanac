"""Admin newsletter campaign routes."""

from __future__ import annotations

import uuid
from datetime import timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.newsletters import (
    NewsletterForm,
    NewsletterScheduleForm,
    NewsletterTestForm,
)
from app.models.enums import NewsletterStatus
from app.services import newsletters as newsletter_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


def _bind_article_choices(form: NewsletterForm) -> None:
    form.article_id.choices = newsletter_service.article_choices()


@admin_bp.route("/newsletters")
@login_required
@staff_required
def newsletter_list():
    processed = newsletter_service.process_due_newsletters()
    if processed:
        flash(f"Sent {processed} scheduled campaign(s) that were due.", "info")

    status = (request.args.get("status") or "ALL").upper()
    filter_status = None if status in ("", "ALL") else status
    items = newsletter_service.list_newsletters(status=filter_status)
    counts = newsletter_service.count_by_status()
    return render_template(
        "admin/newsletters/list.html",
        newsletters=items,
        counts=counts,
        current_status=status if status else "ALL",
        breadcrumbs=[{"label": "Newsletters", "url": None}],
        page_title="Newsletters",
        active_nav="newsletters",
    )


@admin_bp.route("/newsletters/new", methods=["GET", "POST"])
@login_required
@staff_required
def newsletter_create():
    form = NewsletterForm()
    _bind_article_choices(form)
    if form.validate_on_submit():
        try:
            newsletter = newsletter_service.save_newsletter_from_form(form)
        except newsletter_service.NewsletterError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Campaign “{newsletter.subject}” created.", "success")
            return redirect(
                url_for("admin.newsletter_detail", newsletter_id=newsletter.id)
            )
    return render_template(
        "admin/newsletters/form.html",
        form=form,
        newsletter=None,
        breadcrumbs=[
            {"label": "Newsletters", "url": url_for("admin.newsletter_list")},
            {"label": "New", "url": None},
        ],
        page_title="New campaign",
        active_nav="newsletters",
    )


@admin_bp.route("/newsletters/<newsletter_id>", methods=["GET", "POST"])
@login_required
@staff_required
def newsletter_detail(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)

    form = NewsletterForm()
    _bind_article_choices(form)
    schedule_form = NewsletterScheduleForm()
    test_form = NewsletterTestForm()
    editable = newsletter.status != NewsletterStatus.SENDING
    can_send = newsletter.status in (
        NewsletterStatus.DRAFT,
        NewsletterStatus.SCHEDULED,
    )

    if request.method == "GET":
        form.subject.data = newsletter.subject
        form.article_id.data = str(newsletter.article_id) if newsletter.article_id else ""
        form.html_content.data = newsletter.html_content or ""

    if editable and form.validate_on_submit():
        try:
            newsletter = newsletter_service.save_newsletter_from_form(
                form, newsletter=newsletter
            )
        except newsletter_service.NewsletterError as exc:
            flash(str(exc), "error")
        else:
            flash("Campaign saved.", "success")
            return redirect(
                url_for("admin.newsletter_detail", newsletter_id=newsletter.id)
            )

    stats = newsletter_service.delivery_stats(newsletter.id)
    deliveries = newsletter_service.list_deliveries(newsletter.id)
    return render_template(
        "admin/newsletters/detail.html",
        newsletter=newsletter,
        form=form,
        schedule_form=schedule_form,
        test_form=test_form,
        stats=stats,
        deliveries=deliveries,
        editable=editable,
        can_send=can_send,
        breadcrumbs=[
            {"label": "Newsletters", "url": url_for("admin.newsletter_list")},
            {"label": newsletter.subject, "url": None},
        ],
        page_title=newsletter.subject,
        active_nav="newsletters",
    )


@admin_bp.route("/newsletters/<newsletter_id>/preview")
@login_required
@staff_required
def newsletter_preview(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    return render_template(
        "admin/newsletters/preview.html",
        newsletter=newsletter,
        breadcrumbs=[
            {"label": "Newsletters", "url": url_for("admin.newsletter_list")},
            {
                "label": newsletter.subject,
                "url": url_for("admin.newsletter_detail", newsletter_id=newsletter.id),
            },
            {"label": "Preview", "url": None},
        ],
        page_title="Preview",
        active_nav="newsletters",
    )


@admin_bp.route("/newsletters/<newsletter_id>/preview/html")
@login_required
@staff_required
def newsletter_preview_html(newsletter_id: str):
    from flask import Response

    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    return Response(
        newsletter_service.preview_html(newsletter),
        mimetype="text/html; charset=utf-8",
    )


@admin_bp.route("/newsletters/<newsletter_id>/test", methods=["POST"])
@login_required
@staff_required
def newsletter_test(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    form = NewsletterTestForm()
    if form.validate_on_submit():
        try:
            newsletter_service.send_test_email(newsletter, form.email.data)
        except newsletter_service.NewsletterError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Test email sent to {form.email.data}.", "success")
    else:
        flash("Enter a valid test email address.", "error")
    return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))


@admin_bp.route("/newsletters/<newsletter_id>/schedule", methods=["POST"])
@login_required
@staff_required
def newsletter_schedule(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    form = NewsletterScheduleForm()
    if form.validate_on_submit():
        when = form.scheduled_at.data
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        try:
            newsletter_service.schedule_newsletter(newsletter, when)
        except newsletter_service.NewsletterError as exc:
            flash(str(exc), "error")
        else:
            flash("Campaign scheduled.", "success")
    else:
        flash("Pick a valid future date and time.", "error")
    return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))


@admin_bp.route("/newsletters/<newsletter_id>/cancel-schedule", methods=["POST"])
@login_required
@staff_required
def newsletter_cancel_schedule(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    try:
        newsletter_service.cancel_schedule(newsletter)
    except newsletter_service.NewsletterError as exc:
        flash(str(exc), "error")
    else:
        flash("Schedule cancelled — campaign is a draft again.", "info")
    return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))


@admin_bp.route("/newsletters/<newsletter_id>/send", methods=["POST"])
@login_required
@staff_required
def newsletter_send(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    try:
        stats = newsletter_service.send_newsletter_now(newsletter)
    except newsletter_service.NewsletterError as exc:
        flash(str(exc), "error")
    else:
        errors = stats.get("errors") or []
        if stats["failed"]:
            detail = f" First error: {errors[0]}" if errors else ""
            flash(
                f"Campaign finished: {stats['sent']} delivered, {stats['failed']} failed.{detail}",
                "error" if not stats["sent"] else "warning",
            )
        else:
            flash(
                f"Campaign sent: {stats['sent']} delivered, {stats['failed']} failed.",
                "success",
            )
    return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))


@admin_bp.route("/newsletters/<newsletter_id>/retry-failed", methods=["POST"])
@login_required
@staff_required
def newsletter_retry_failed(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    try:
        stats = newsletter_service.retry_failed_deliveries(newsletter)
    except newsletter_service.NewsletterError as exc:
        flash(str(exc), "error")
    else:
        errors = stats.get("errors") or []
        detail = f" First error: {errors[0]}" if errors else ""
        flash(
            f"Retry finished: {stats['sent']} delivered, {stats['failed']} failed.{detail}",
            "success" if stats["sent"] and not stats["failed"] else "warning",
        )
    return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))


@admin_bp.route("/newsletters/<newsletter_id>/delete", methods=["POST"])
@login_required
@staff_required
def newsletter_delete(newsletter_id: str):
    newsletter = newsletter_service.get_newsletter(_parse_uuid(newsletter_id))
    if newsletter is None:
        abort(404)
    try:
        newsletter_service.delete_newsletter(newsletter)
    except newsletter_service.NewsletterError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.newsletter_detail", newsletter_id=newsletter.id))
    flash("Campaign deleted.", "info")
    return redirect(url_for("admin.newsletter_list"))
