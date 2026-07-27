"""Category and tag management routes."""

from __future__ import annotations

import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.taxonomy import CategoryForm, TagForm
from app.services import taxonomy as taxonomy_service
from app.services.publications import get_or_create_default_publication


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


@admin_bp.route("/categories")
@login_required
@staff_required
def category_list():
    publication = get_or_create_default_publication()
    categories = taxonomy_service.list_categories(publication.id)
    return render_template(
        "admin/categories/list.html",
        categories=categories,
        breadcrumbs=[{"label": "Categories", "url": None}],
        page_title="Categories",
        active_nav="categories",
    )


@admin_bp.route("/categories/new", methods=["GET", "POST"])
@login_required
@staff_required
def category_create():
    form = CategoryForm()
    if form.validate_on_submit():
        category = taxonomy_service.save_category_from_form(form)
        flash(f"Category “{category.name}” created.", "success")
        return redirect(url_for("admin.category_list"))
    return render_template(
        "admin/categories/form.html",
        form=form,
        category=None,
        breadcrumbs=[
            {"label": "Categories", "url": url_for("admin.category_list")},
            {"label": "New", "url": None},
        ],
        page_title="New category",
        active_nav="categories",
    )


@admin_bp.route("/categories/<category_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def category_edit(category_id: str):
    category = taxonomy_service.get_category(_parse_uuid(category_id))
    if category is None:
        abort(404)

    form = CategoryForm()
    if request.method == "GET":
        form.name.data = category.name
        form.slug.data = category.slug
        form.description.data = category.description

    if form.validate_on_submit():
        category = taxonomy_service.save_category_from_form(form, category=category)
        flash(f"Category “{category.name}” saved.", "success")
        return redirect(url_for("admin.category_list"))

    return render_template(
        "admin/categories/form.html",
        form=form,
        category=category,
        breadcrumbs=[
            {"label": "Categories", "url": url_for("admin.category_list")},
            {"label": category.name, "url": None},
        ],
        page_title="Edit category",
        active_nav="categories",
    )


@admin_bp.route("/categories/<category_id>/delete", methods=["POST"])
@login_required
@staff_required
def category_delete(category_id: str):
    category = taxonomy_service.get_category(_parse_uuid(category_id))
    if category is None:
        abort(404)
    name = category.name
    taxonomy_service.delete_category(category)
    flash(f"Category “{name}” deleted.", "info")
    return redirect(url_for("admin.category_list"))


@admin_bp.route("/tags")
@login_required
@staff_required
def tag_list():
    publication = get_or_create_default_publication()
    tags = taxonomy_service.list_tags(publication.id)
    return render_template(
        "admin/tags/list.html",
        tags=tags,
        breadcrumbs=[{"label": "Tags", "url": None}],
        page_title="Tags",
        active_nav="tags",
    )


@admin_bp.route("/tags/new", methods=["GET", "POST"])
@login_required
@staff_required
def tag_create():
    form = TagForm()
    if form.validate_on_submit():
        tag = taxonomy_service.save_tag_from_form(form)
        flash(f"Tag “{tag.name}” created.", "success")
        return redirect(url_for("admin.tag_list"))
    return render_template(
        "admin/tags/form.html",
        form=form,
        tag=None,
        breadcrumbs=[
            {"label": "Tags", "url": url_for("admin.tag_list")},
            {"label": "New", "url": None},
        ],
        page_title="New tag",
        active_nav="tags",
    )


@admin_bp.route("/tags/<tag_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def tag_edit(tag_id: str):
    tag = taxonomy_service.get_tag(_parse_uuid(tag_id))
    if tag is None:
        abort(404)

    form = TagForm()
    if request.method == "GET":
        form.name.data = tag.name
        form.slug.data = tag.slug

    if form.validate_on_submit():
        tag = taxonomy_service.save_tag_from_form(form, tag=tag)
        flash(f"Tag “{tag.name}” saved.", "success")
        return redirect(url_for("admin.tag_list"))

    return render_template(
        "admin/tags/form.html",
        form=form,
        tag=tag,
        breadcrumbs=[
            {"label": "Tags", "url": url_for("admin.tag_list")},
            {"label": tag.name, "url": None},
        ],
        page_title="Edit tag",
        active_nav="tags",
    )


@admin_bp.route("/tags/<tag_id>/delete", methods=["POST"])
@login_required
@staff_required
def tag_delete(tag_id: str):
    tag = taxonomy_service.get_tag(_parse_uuid(tag_id))
    if tag is None:
        abort(404)
    name = tag.name
    taxonomy_service.delete_tag(tag)
    flash(f"Tag “{name}” deleted.", "info")
    return redirect(url_for("admin.tag_list"))
