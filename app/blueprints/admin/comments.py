"""Admin comment moderation."""

from __future__ import annotations

import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.services import engagement as engagement_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


@admin_bp.route("/comments")
@login_required
@staff_required
def comment_list():
    status = (request.args.get("status") or "pending").lower()
    if status not in {"all", "pending", "approved"}:
        status = "pending"
    q = (request.args.get("q") or "").strip() or None
    filter_status = None if status == "all" else status
    items = engagement_service.list_comments_admin(status=filter_status, q=q)
    counts = engagement_service.count_comments_by_status()
    return render_template(
        "admin/comments/list.html",
        comments=items,
        counts=counts,
        current_status=status,
        q=q or "",
        breadcrumbs=[{"label": "Comments", "url": None}],
        page_title="Comments",
        active_nav="comments",
    )


@admin_bp.route("/comments/<comment_id>/approve", methods=["POST"])
@login_required
@staff_required
def comment_approve(comment_id: str):
    comment = engagement_service.get_comment(_parse_uuid(comment_id))
    if comment is None:
        abort(404)
    engagement_service.set_comment_approved(comment, approved=True)
    flash("Comment approved.", "success")
    return redirect(request.referrer or url_for("admin.comment_list"))


@admin_bp.route("/comments/<comment_id>/unapprove", methods=["POST"])
@login_required
@staff_required
def comment_unapprove(comment_id: str):
    comment = engagement_service.get_comment(_parse_uuid(comment_id))
    if comment is None:
        abort(404)
    engagement_service.set_comment_approved(comment, approved=False)
    flash("Comment moved back to pending.", "success")
    return redirect(request.referrer or url_for("admin.comment_list"))


@admin_bp.route("/comments/<comment_id>/delete", methods=["POST"])
@login_required
@staff_required
def comment_delete(comment_id: str):
    comment = engagement_service.get_comment(_parse_uuid(comment_id))
    if comment is None:
        abort(404)
    engagement_service.delete_comment(comment)
    flash("Comment deleted.", "success")
    return redirect(request.referrer or url_for("admin.comment_list"))
