"""Article management routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.extensions import db, limiter
from app.forms.article import ArticleForm
from app.models.enums import ArticleStatus
from app.services import articles as article_service
from app.services import taxonomy as taxonomy_service
from app.services.media import MediaUploadError, media_public_url, save_image_upload
from app.services.publications import get_or_create_default_publication


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


def _bind_taxonomy_choices(form: ArticleForm, publication_id: uuid.UUID) -> None:
    from app.services import projects as project_service

    categories, tags = taxonomy_service.taxonomy_choices(publication_id)
    form.categories.choices = categories
    form.tags.choices = tags
    form.project_id.choices = [
        ("", "— None —"),
        *[
            (str(project.id), project.title)
            for project in project_service.list_projects_admin()
            if project.publication_id == publication_id
        ],
    ]


def _populate_form(form: ArticleForm, article) -> None:
    form.title.data = article.title
    form.subtitle.data = article.subtitle
    form.slug.data = article.slug
    form.excerpt.data = article.excerpt
    form.content.data = article.content
    form.reading_time.data = article.reading_time
    form.status.data = article.status.value
    form.seo_title.data = article.seo_title
    form.seo_description.data = article.seo_description
    form.canonical_url.data = article.canonical_url
    form.featured.data = article.featured
    form.allow_comments.data = article.allow_comments
    form.published_at.data = _to_local_naive(article.published_at)
    form.scheduled_at.data = _to_local_naive(article.scheduled_at)
    form.categories.data = [str(c.id) for c in article.categories]
    form.tags.data = [str(t.id) for t in article.tags]
    form.project_id.data = str(article.project_id) if article.project_id else ""


def _to_local_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


@admin_bp.route("/articles/editor/upload", methods=["POST"])
@login_required
@staff_required
@limiter.limit("60 per minute")
def article_editor_upload():
    """Drag-and-drop / picker image upload for the rich text editor."""
    file = request.files.get("file")
    try:
        media = save_image_upload(file, current_user)
        db.session.commit()
    except MediaUploadError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": "Upload failed."}), 500

    return jsonify({"location": media_public_url(media)})


@admin_bp.route("/articles")
@login_required
@staff_required
def article_list():
    status = (request.args.get("status") or "").strip().upper() or None
    if status == "ALL":
        status = None
    articles = article_service.list_articles(status=status)
    counts = article_service.count_by_status()
    return render_template(
        "admin/articles/list.html",
        articles=articles,
        counts=counts,
        current_status=status or "ALL",
        breadcrumbs=[
            {"label": "Articles", "url": None},
        ],
        page_title="Articles",
        active_nav="articles",
    )


@admin_bp.route("/articles/new", methods=["GET", "POST"])
@login_required
@staff_required
def article_create():
    publication = get_or_create_default_publication()
    form = ArticleForm()
    _bind_taxonomy_choices(form, publication.id)
    if request.method == "GET":
        form.status.data = ArticleStatus.DRAFT.value
        form.allow_comments.data = True

    if form.validate_on_submit():
        article = article_service.save_article_from_form(form, author=current_user)
        flash(f"Article “{article.title}” created.", "success")
        return redirect(url_for("admin.article_edit", article_id=article.id))

    return render_template(
        "admin/articles/form.html",
        form=form,
        article=None,
        breadcrumbs=[
            {"label": "Articles", "url": url_for("admin.article_list")},
            {"label": "New", "url": None},
        ],
        page_title="New article",
        active_nav="articles",
    )


@admin_bp.route("/articles/<article_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def article_edit(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)

    form = ArticleForm()
    _bind_taxonomy_choices(form, article.publication_id)
    if request.method == "GET":
        _populate_form(form, article)

    if form.validate_on_submit():
        article = article_service.save_article_from_form(
            form,
            author=current_user,
            article=article,
        )
        flash(f"Article “{article.title}” saved.", "success")
        return redirect(url_for("admin.article_edit", article_id=article.id))

    return render_template(
        "admin/articles/form.html",
        form=form,
        article=article,
        breadcrumbs=[
            {"label": "Articles", "url": url_for("admin.article_list")},
            {"label": article.title, "url": None},
        ],
        page_title="Edit article",
        active_nav="articles",
    )


@admin_bp.route("/articles/<article_id>/delete", methods=["POST"])
@login_required
@staff_required
def article_delete(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)
    title = article.title
    article_service.delete_article(article)
    flash(f"Article “{title}” deleted.", "info")
    return redirect(url_for("admin.article_list"))


@admin_bp.route("/articles/<article_id>/publish", methods=["POST"])
@login_required
@staff_required
def article_publish(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)
    article_service.set_article_status(article, ArticleStatus.PUBLISHED)
    flash(f"“{article.title}” is now published.", "success")
    return redirect(request.referrer or url_for("admin.article_list"))


@admin_bp.route("/articles/<article_id>/archive", methods=["POST"])
@login_required
@staff_required
def article_archive(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)
    article_service.set_article_status(article, ArticleStatus.ARCHIVED)
    flash(f"“{article.title}” archived.", "info")
    return redirect(request.referrer or url_for("admin.article_list"))


@admin_bp.route("/articles/<article_id>/draft", methods=["POST"])
@login_required
@staff_required
def article_draft(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)
    article_service.set_article_status(article, ArticleStatus.DRAFT)
    flash(f"“{article.title}” moved to drafts.", "info")
    return redirect(request.referrer or url_for("admin.article_list"))


@admin_bp.route("/articles/<article_id>/preview")
@login_required
@staff_required
def article_preview(article_id: str):
    article = article_service.get_article(_parse_uuid(article_id))
    if article is None:
        abort(404)
    return render_template(
        "admin/articles/preview.html",
        article=article,
        breadcrumbs=[
            {"label": "Articles", "url": url_for("admin.article_list")},
            {"label": article.title, "url": url_for("admin.article_edit", article_id=article.id)},
            {"label": "Preview", "url": None},
        ],
        page_title="Preview",
        active_nav="articles",
    )
