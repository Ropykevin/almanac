"""Admin research projects routes."""

from __future__ import annotations

import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.projects import ProjectDocumentForm, ProjectForm
from app.services import projects as project_service
from app.services.media import media_kind, media_public_url


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


def _document_rows(project) -> list[dict]:
    rows = []
    for document in project_service.list_project_documents(project):
        media = document.media
        rows.append(
            {
                "id": document.id,
                "title": document.display_title,
                "url": media_public_url(media) if media else None,
                "kind": media_kind(media) if media else "document",
                "size_label": project_service.format_file_size(
                    media.size if media else None
                ),
                "original_name": media.original_name if media else "",
            }
        )
    return rows


@admin_bp.route("/projects")
@login_required
@staff_required
def project_list():
    items = project_service.list_projects_admin()
    return render_template(
        "admin/projects/list.html",
        projects=items,
        breadcrumbs=[{"label": "Projects", "url": None}],
        page_title="Projects",
        active_nav="projects",
    )


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
@staff_required
def project_create():
    form = ProjectForm()
    if form.validate_on_submit():
        try:
            project = project_service.save_project_from_form(form)
        except project_service.ProjectError as exc:
            flash(str(exc), "error")
        else:
            flash(
                f"Project “{project.title}” created. You can upload documents below.",
                "success",
            )
            return redirect(url_for("admin.project_edit", project_id=project.id))
    return render_template(
        "admin/projects/form.html",
        form=form,
        document_form=None,
        documents=[],
        project=None,
        breadcrumbs=[
            {"label": "Projects", "url": url_for("admin.project_list")},
            {"label": "New", "url": None},
        ],
        page_title="New project",
        active_nav="projects",
    )


@admin_bp.route("/projects/<project_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def project_edit(project_id: str):
    project = project_service.get_project(_parse_uuid(project_id))
    if project is None:
        abort(404)

    form = ProjectForm()
    document_form = ProjectDocumentForm()
    if request.method == "GET":
        form.title.data = project.title
        form.slug.data = project.slug
        form.description.data = project.description
        form.body.data = project.body or ""
        form.status.data = project.status.value
        form.sort_order.data = project.sort_order
        form.is_published.data = project.is_published

    if form.validate_on_submit():
        try:
            project = project_service.save_project_from_form(form, project=project)
        except project_service.ProjectError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Project “{project.title}” saved.", "success")
            return redirect(url_for("admin.project_edit", project_id=project.id))

    return render_template(
        "admin/projects/form.html",
        form=form,
        document_form=document_form,
        documents=_document_rows(project),
        project=project,
        breadcrumbs=[
            {"label": "Projects", "url": url_for("admin.project_list")},
            {"label": project.title, "url": None},
        ],
        page_title=f"Edit {project.title}",
        active_nav="projects",
    )


@admin_bp.route("/projects/<project_id>/documents", methods=["POST"])
@login_required
@staff_required
def project_document_upload(project_id: str):
    project = project_service.get_project(_parse_uuid(project_id))
    if project is None:
        abort(404)

    form = ProjectDocumentForm()
    if form.validate_on_submit():
        try:
            document = project_service.add_project_document(
                project,
                form.file.data,
                current_user,
                title=form.title.data,
            )
        except project_service.ProjectError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Uploaded “{document.display_title}”.", "success")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "error")
                break
            break
        else:
            flash("Could not upload that document.", "error")

    return redirect(url_for("admin.project_edit", project_id=project.id))


@admin_bp.route(
    "/projects/<project_id>/documents/<document_id>/delete",
    methods=["POST"],
)
@login_required
@staff_required
def project_document_delete(project_id: str, document_id: str):
    project = project_service.get_project(_parse_uuid(project_id))
    if project is None:
        abort(404)
    document = project_service.get_project_document(
        _parse_uuid(document_id),
        project_id=project.id,
    )
    if document is None:
        abort(404)

    title = document.display_title
    project_service.delete_project_document(document)
    flash(f"Removed “{title}”.", "success")
    return redirect(url_for("admin.project_edit", project_id=project.id))


@admin_bp.route("/projects/<project_id>/delete", methods=["POST"])
@login_required
@staff_required
def project_delete(project_id: str):
    project = project_service.get_project(_parse_uuid(project_id))
    if project is None:
        abort(404)
    title = project.title
    project_service.delete_project(project)
    flash(f"Project “{title}” deleted.", "success")
    return redirect(url_for("admin.project_list"))
