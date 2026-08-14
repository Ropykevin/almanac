"""Research projects service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Project, ProjectDocument, User
from app.models.enums import ProjectStatus
from app.services.media import MediaUploadError, delete_media, media_public_url, save_upload
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity
from app.utils.html_sanitize import sanitize_article_html
from app.utils.slug import unique_project_slug


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
    return db.session.scalars(
        select(Project)
        .options(joinedload(Project.documents).joinedload(ProjectDocument.media))
        .where(
            Project.publication_id == publication.id,
            Project.slug == slug,
            Project.is_published.is_(True),
        )
    ).unique().first()


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
        # Do not add() until required fields (especially slug) are set —
        # unique_project_slug() queries and would autoflush a null slug.
        project = Project(publication_id=publication.id)

    project.title = title[:255]
    project.description = description
    project.body = sanitize_article_html(body) if body else None
    project.status = status
    project.sort_order = sort_order
    project.is_published = bool(form.is_published.data)
    with db.session.no_autoflush:
        project.slug = unique_project_slug(
            publication.id,
            title,
            desired=desired_slug,
            exclude_id=None if created else project.id,
        )

    if created:
        db.session.add(project)

    log_activity(
        "project.created" if created else "project.updated",
        f"{'Created' if created else 'Updated'} project “{project.title}”",
    )
    db.session.commit()
    return project


def delete_project(project: Project) -> None:
    title = project.title
    documents = list_project_documents(project)
    media_ids = [doc.media_id for doc in documents]
    for doc in documents:
        db.session.delete(doc)
    db.session.flush()
    db.session.delete(project)
    log_activity("project.deleted", f"Deleted project “{title}”")
    db.session.commit()

    from app.models import Media

    for media_id in media_ids:
        media = db.session.get(Media, media_id)
        if media is not None:
            try:
                delete_media(media)
            except Exception:  # noqa: BLE001
                pass


def list_project_documents(project: Project) -> list[ProjectDocument]:
    return list(
        db.session.scalars(
            select(ProjectDocument)
            .options(joinedload(ProjectDocument.media))
            .where(ProjectDocument.project_id == project.id)
            .order_by(
                ProjectDocument.sort_order.asc(),
                ProjectDocument.created_at.asc(),
            )
        ).all()
    )


def get_project_document(
    document_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> ProjectDocument | None:
    stmt = (
        select(ProjectDocument)
        .options(joinedload(ProjectDocument.media))
        .where(ProjectDocument.id == document_id)
    )
    if project_id is not None:
        stmt = stmt.where(ProjectDocument.project_id == project_id)
    return db.session.scalar(stmt)


def add_project_document(
    project: Project,
    file: FileStorage,
    uploader: User,
    *,
    title: str | None = None,
) -> ProjectDocument:
    try:
        media = save_upload(file, uploader)
    except MediaUploadError as exc:
        raise ProjectError(str(exc)) from exc

    max_order = db.session.scalar(
        select(func.max(ProjectDocument.sort_order)).where(
            ProjectDocument.project_id == project.id
        )
    )
    display = (title or "").strip() or media.original_name
    document = ProjectDocument(
        project_id=project.id,
        media_id=media.id,
        title=display[:255] if display else None,
        sort_order=(max_order or 0) + 1,
    )
    db.session.add(document)
    log_activity(
        "project.document_added",
        f"Added document “{document.title or media.original_name}” to “{project.title}”",
    )
    db.session.commit()
    return document


def delete_project_document(document: ProjectDocument) -> None:
    media = document.media
    label = document.display_title
    project_title = document.project.title if document.project else "project"
    db.session.delete(document)
    log_activity(
        "project.document_removed",
        f"Removed document “{label}” from “{project_title}”",
    )
    db.session.commit()
    if media is not None:
        delete_media(media)


def list_published_articles_for_project(project: Project) -> list:
    """Published essays attached to a project, newest first."""
    from app.models import Article
    from app.models.enums import ArticleStatus

    return list(
        db.session.scalars(
            select(Article)
            .options(joinedload(Article.author))
            .where(
                Article.project_id == project.id,
                Article.status == ArticleStatus.PUBLISHED,
            )
            .order_by(Article.published_at.desc(), Article.created_at.desc())
        ).all()
    )


def document_public_url(document: ProjectDocument) -> str | None:
    if document.media is None:
        return None
    return media_public_url(document.media)


def format_file_size(size: int | None) -> str:
    if not size or size < 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"
