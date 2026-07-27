"""Admin media library routes."""

from __future__ import annotations

import uuid

from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.extensions import db, limiter
from app.forms.media import MediaEditForm, MediaUploadForm
from app.services import media as media_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


def _media_payload(item) -> dict:
    return {
        "id": str(item.id),
        "url": media_service.media_public_url(item),
        "original_name": item.original_name,
        "alt_text": item.alt_text or "",
        "mime_type": item.mime_type,
        "kind": media_service.media_kind(item),
        "size": item.size,
        "size_label": media_service.format_size(item.size),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@admin_bp.route("/media")
@login_required
@staff_required
def media_list():
    q = (request.args.get("q") or "").strip() or None
    kind = (request.args.get("kind") or "all").lower()
    try:
        page = int(request.args.get("page") or 1)
    except ValueError:
        page = 1

    result = media_service.list_media(q=q, kind=kind, page=page, per_page=24)
    return render_template(
        "admin/media/list.html",
        page_data=result,
        breadcrumbs=[{"label": "Media", "url": None}],
        page_title="Media library",
        active_nav="media",
    )


@admin_bp.route("/media/upload", methods=["GET", "POST"])
@login_required
@staff_required
@limiter.limit("30 per minute")
def media_upload():
    form = MediaUploadForm()
    if form.validate_on_submit():
        try:
            media = media_service.save_upload(
                form.file.data,
                current_user,
                alt_text=form.alt_text.data,
            )
            db.session.commit()
        except media_service.MediaUploadError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Uploaded “{media.original_name}”.", "success")
            return redirect(url_for("admin.media_detail", media_id=media.id))
    return render_template(
        "admin/media/upload.html",
        form=form,
        breadcrumbs=[
            {"label": "Media", "url": url_for("admin.media_list")},
            {"label": "Upload", "url": None},
        ],
        page_title="Upload media",
        active_nav="media",
    )


@admin_bp.route("/media/<media_id>", methods=["GET", "POST"])
@login_required
@staff_required
def media_detail(media_id: str):
    media = media_service.get_media(_parse_uuid(media_id))
    if media is None:
        abort(404)

    form = MediaEditForm()
    if request.method == "GET":
        form.alt_text.data = media.alt_text or ""

    if form.validate_on_submit():
        try:
            if form.file.data and form.file.data.filename:
                media_service.replace_media_file(media, form.file.data)
            media_service.update_media_meta(
                media,
                alt_text=form.alt_text.data,
                commit=False,
            )
            db.session.commit()
        except media_service.MediaUploadError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        else:
            flash("Media updated.", "success")
            return redirect(url_for("admin.media_detail", media_id=media.id))

    return render_template(
        "admin/media/detail.html",
        media=media,
        form=form,
        kind=media_service.media_kind(media),
        public_url=media_service.media_public_url(media),
        size_label=media_service.format_size(media.size),
        breadcrumbs=[
            {"label": "Media", "url": url_for("admin.media_list")},
            {"label": media.original_name, "url": None},
        ],
        page_title=media.original_name,
        active_nav="media",
    )


@admin_bp.route("/media/<media_id>/delete", methods=["POST"])
@login_required
@staff_required
def media_delete(media_id: str):
    media = media_service.get_media(_parse_uuid(media_id))
    if media is None:
        abort(404)
    name = media.original_name
    media_service.delete_media(media)
    flash(f"Deleted “{name}”.", "info")
    return redirect(url_for("admin.media_list"))


@admin_bp.route("/media/picker")
@login_required
@staff_required
def media_picker():
    """Compact picker UI for the article editor (postMessage)."""
    q = (request.args.get("q") or "").strip() or None
    kind = (request.args.get("kind") or "image").lower()
    try:
        page = int(request.args.get("page") or 1)
    except ValueError:
        page = 1
    result = media_service.list_media(q=q, kind=kind, page=page, per_page=18)
    return render_template(
        "admin/media/picker.html",
        page_data=result,
        kind=kind,
        q=q or "",
    )


@admin_bp.route("/media/api")
@login_required
@staff_required
def media_api():
    """JSON listing for editor integrations."""
    q = (request.args.get("q") or "").strip() or None
    kind = (request.args.get("kind") or "all").lower()
    try:
        page = int(request.args.get("page") or 1)
    except ValueError:
        page = 1
    result = media_service.list_media(q=q, kind=kind, page=page, per_page=24)
    return jsonify(
        {
            "items": [_media_payload(item) for item in result.items],
            "page": result.page,
            "pages": result.pages,
            "total": result.total,
            "kind": result.kind,
            "q": result.q,
        }
    )


@admin_bp.route("/media/api/upload", methods=["POST"])
@login_required
@staff_required
@limiter.limit("60 per minute")
def media_api_upload():
    """JSON upload used by the library dropzone / editor."""
    file = request.files.get("file")
    images_only = request.args.get("images_only") == "1"
    try:
        media = media_service.save_upload(
            file,
            current_user,
            alt_text=request.form.get("alt_text"),
            images_only=images_only,
        )
        db.session.commit()
    except media_service.MediaUploadError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": "Upload failed."}), 500
    return jsonify(_media_payload(media))
