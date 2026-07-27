"""Research projects service."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import Project
from app.models.enums import ProjectStatus
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity
from app.utils.slug import unique_project_slug
from app.utils.html_sanitize import sanitize_article_html


class ProjectError(ValueError):
    """Invalid project input."""


def list_projects_admin() -> list[Project]:
    publication = get_or_create_default_publication()
    return list(
        db.session.scalars(
            select(Project)
            .where(Project.publication_id == publication.id)
            .order_by(Project.sort_order.asc(), Project.title.asc())
        ).all()
    )


def list_published_projects(*, limit: int | None = None) -> list[Project]:
    publication = get_or_create_default_publication()
    stmt = (
        select(Project)
        .where(
            Project.publication_id == publication.id,
            Project.is_published.is_(True),
        )
        .order_by(Project.created_at.desc(), Project.title.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.session.scalars(stmt).all())


def list_published_projects_ordered(*, limit: int | None = None) -> list[Project]:
    """Published projects by manual sort order (Projects page)."""
    publication = get_or_create_default_publication()
    stmt = (
        select(Project)
        .where(
            Project.publication_id == publication.id,
            Project.is_published.is_(True),
        )
        .order_by(Project.sort_order.asc(), Project.title.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.session.scalars(stmt).all())


def get_project(project_id: uuid.UUID) -> Project | None:
    return db.session.scalar(select(Project).where(Project.id == project_id))


def get_published_project_by_slug(slug: str) -> Project | None:
    publication = get_or_create_default_publication()
    return db.session.scalar(
        select(Project).where(
            Project.publication_id == publication.id,
            Project.slug == slug,
            Project.is_published.is_(True),
        )
    )


def save_project_from_form(form, *, project: Project | None = None) -> Project:
    title = (form.title.data or "").strip()
    description = (form.description.data or "").strip()
    body = (form.body.data or "").strip() or None
    desired_slug = (form.slug.data or "").strip() or None
    if not title:
        raise ProjectError("Title is required.")
    if not description:
        raise ProjectError("Description is required.")

    try:
        status = ProjectStatus(form.status.data)
    except ValueError as exc:
        raise ProjectError("Invalid status.") from exc

    try:
        sort_order = int(form.sort_order.data or 0)
    except (TypeError, ValueError):
        sort_order = 0

    publication = get_or_create_default_publication()
    created = project is None
    if project is None:
        project = Project(publication_id=publication.id)
        db.session.add(project)

    project.title = title[:255]
    project.slug = unique_project_slug(
        publication.id,
        title,
        desired=desired_slug,
        exclude_id=None if created else project.id,
    )
    project.description = description
    project.body = sanitize_article_html(body) if body else None
    project.status = status
    project.sort_order = sort_order
    project.is_published = bool(form.is_published.data)

    log_activity(
        "project.created" if created else "project.updated",
        f"{'Created' if created else 'Updated'} project “{project.title}”",
    )
    db.session.commit()
    return project


def delete_project(project: Project) -> None:
    title = project.title
    db.session.delete(project)
    log_activity("project.deleted", f"Deleted project “{title}”")
    db.session.commit()
