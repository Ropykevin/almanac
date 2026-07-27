"""Admin research projects routes."""

from __future__ import annotations

import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.projects import ProjectForm
from app.services import projects as project_service


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        abort(404)


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
            flash(f"Project “{project.title}” created.", "success")
            return redirect(url_for("admin.project_list"))
    return render_template(
        "admin/projects/form.html",
        form=form,
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
            return redirect(url_for("admin.project_list"))

    return render_template(
        "admin/projects/form.html",
        form=form,
        project=project,
        breadcrumbs=[
            {"label": "Projects", "url": url_for("admin.project_list")},
            {"label": project.title, "url": None},
        ],
        page_title=f"Edit {project.title}",
        active_nav="projects",
    )


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
