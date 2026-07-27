"""Model metadata smoke checks (SQLite in-memory)."""

import uuid

from app.extensions import db
from app.models import (
    Article,
    ArticleStatus,
    Category,
    Media,
    Publication,
    Tag,
    User,
    UserRole,
)


def test_create_publication_graph(app):
    with app.app_context():
        user = User(
            full_name="Editor User",
            email="editor@example.com",
            role=UserRole.EDITOR,
            is_active=True,
            email_verified=True,
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        media = Media(
            uploaded_by=user.id,
            file_name="cover.webp",
            original_name="cover.webp",
            mime_type="image/webp",
            size=1024,
            path="uploads/cover.webp",
        )
        db.session.add(media)
        db.session.flush()

        publication = Publication(
            name="Liminal Weekly",
            slug="liminal-weekly",
            logo_id=media.id,
        )
        db.session.add(publication)
        db.session.flush()

        category = Category(
            publication_id=publication.id,
            name="AI",
            slug="ai",
        )
        tag = Tag(
            publication_id=publication.id,
            name="Africa",
            slug="africa",
        )
        db.session.add_all([category, tag])
        db.session.flush()

        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title="Hello Africa",
            slug="hello-africa",
            status=ArticleStatus.DRAFT,
            featured=False,
            allow_comments=True,
            featured_image=media.id,
        )
        article.categories.append(category)
        article.tags.append(tag)
        db.session.add(article)
        db.session.commit()

        loaded = db.session.get(Article, article.id)
        assert loaded is not None
        assert loaded.author.email == "editor@example.com"
        assert loaded.publication.slug == "liminal-weekly"
        assert {c.slug for c in loaded.categories} == {"ai"}
        assert {t.slug for t in loaded.tags} == {"africa"}
        assert isinstance(loaded.id, uuid.UUID)


def test_all_model_tables_registered(app):
    expected = {
        "users",
        "publications",
        "publication_users",
        "media",
        "categories",
        "tags",
        "articles",
        "article_tags",
        "article_categories",
        "subscribers",
        "newsletters",
        "newsletter_deliveries",
        "comments",
        "article_views",
        "article_revisions",
        "activity_logs",
        "settings",
    }
    assert expected.issubset(set(db.metadata.tables.keys()))
