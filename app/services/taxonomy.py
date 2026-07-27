"""Category and tag management."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.forms.taxonomy import CategoryForm, TagForm
from app.models import Category, Tag
from app.services.publications import get_or_create_default_publication
from app.utils.activity import log_activity
from app.utils.slug import unique_category_slug, unique_tag_slug


def list_categories(publication_id: uuid.UUID | None = None) -> list[Category]:
    stmt = (
        select(Category)
        .options(joinedload(Category.articles))
        .order_by(Category.name.asc())
    )
    if publication_id is not None:
        stmt = stmt.where(Category.publication_id == publication_id)
    return list(db.session.scalars(stmt).unique().all())


def list_tags(publication_id: uuid.UUID | None = None) -> list[Tag]:
    stmt = select(Tag).options(joinedload(Tag.articles)).order_by(Tag.name.asc())
    if publication_id is not None:
        stmt = stmt.where(Tag.publication_id == publication_id)
    return list(db.session.scalars(stmt).unique().all())


def get_category(category_id: uuid.UUID) -> Category | None:
    return db.session.get(Category, category_id)


def get_tag(tag_id: uuid.UUID) -> Tag | None:
    return db.session.get(Tag, tag_id)


def taxonomy_choices(publication_id: uuid.UUID) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    categories = [
        (str(c.id), c.name)
        for c in list_categories(publication_id)
    ]
    tags = [(str(t.id), t.name) for t in list_tags(publication_id)]
    return categories, tags


def save_category_from_form(
    form: CategoryForm,
    *,
    category: Category | None = None,
) -> Category:
    publication = get_or_create_default_publication()
    is_new = category is None
    name = form.name.data.strip()

    if is_new:
        category = Category(
            publication_id=publication.id,
            name=name,
            slug="temp",
        )
        db.session.add(category)
        publication_id = publication.id
    else:
        category.name = name
        publication_id = category.publication_id

    category.description = (form.description.data or "").strip() or None
    category.slug = unique_category_slug(
        publication_id,
        name,
        desired=form.slug.data,
        exclude_id=None if is_new else category.id,
    )
    log_activity(
        "category.created" if is_new else "category.updated",
        f"{'Created' if is_new else 'Updated'} category “{category.name}”",
    )
    db.session.commit()
    return category


def save_tag_from_form(form: TagForm, *, tag: Tag | None = None) -> Tag:
    publication = get_or_create_default_publication()
    is_new = tag is None
    name = form.name.data.strip()

    if is_new:
        tag = Tag(
            publication_id=publication.id,
            name=name,
            slug="temp",
        )
        db.session.add(tag)
        publication_id = publication.id
    else:
        tag.name = name
        publication_id = tag.publication_id

    tag.slug = unique_tag_slug(
        publication_id,
        name,
        desired=form.slug.data,
        exclude_id=None if is_new else tag.id,
    )
    log_activity(
        "tag.created" if is_new else "tag.updated",
        f"{'Created' if is_new else 'Updated'} tag “{tag.name}”",
    )
    db.session.commit()
    return tag


def delete_category(category: Category) -> None:
    name = category.name
    category.articles.clear()
    log_activity("category.deleted", f"Deleted category “{name}”")
    db.session.delete(category)
    db.session.commit()


def delete_tag(tag: Tag) -> None:
    name = tag.name
    tag.articles.clear()
    log_activity("tag.deleted", f"Deleted tag “{name}”")
    db.session.delete(tag)
    db.session.commit()
