"""Article management tests."""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Article, ArticleStatus, Publication
from app.utils.slug import slugify, unique_article_slug


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def test_slugify_basic():
    assert slugify("Hello, Africa!") == "hello-africa"


def test_article_list_requires_login(client):
    response = client.get("/admin/articles")
    assert response.status_code in {302, 401}


def test_create_and_publish_article(client, editor, app):
    _login(client)

    response = client.post(
        "/admin/articles/new",
        data={
            "title": "Sunrise Over Lagos",
            "subtitle": "A morning dispatch",
            "slug": "",
            "excerpt": "Short excerpt",
            "content": "Word " * 400,
            "status": "DRAFT",
            "featured": False,
            "allow_comments": True,
            "submit": "Save article",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Sunrise Over Lagos" in response.data

    with app.app_context():
        article = Article.query.filter_by(slug="sunrise-over-lagos").first()
        assert article is not None
        assert article.status == ArticleStatus.DRAFT
        assert article.reading_time >= 1
        article_id = article.id

    publish = client.post(f"/admin/articles/{article_id}/publish", follow_redirects=True)
    assert publish.status_code == 200
    assert b"published" in publish.data.lower()

    with app.app_context():
        article = db.session.get(Article, article_id)
        assert article.status == ArticleStatus.PUBLISHED
        assert article.published_at is not None


def test_schedule_requires_datetime(client, editor):
    _login(client)
    response = client.post(
        "/admin/articles/new",
        data={
            "title": "Later Story",
            "status": "SCHEDULED",
            "submit": "Save article",
        },
    )
    assert response.status_code == 200
    assert b"schedule" in response.data.lower()


def test_schedule_article(client, editor, app):
    _login(client)
    when = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        "/admin/articles/new",
        data={
            "title": "Scheduled Story",
            "status": "SCHEDULED",
            "scheduled_at": when,
            "content": "Coming soon",
            "allow_comments": True,
            "submit": "Save article",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        article = Article.query.filter_by(slug="scheduled-story").first()
        assert article is not None
        assert article.status == ArticleStatus.SCHEDULED
        assert article.scheduled_at is not None


def test_unique_slug_per_publication(app, editor):
    with app.app_context():
        pub = Publication(name="Main", slug="main")
        db.session.add(pub)
        db.session.flush()
        first = Article(
            publication_id=pub.id,
            author_id=editor.id,
            title="Same",
            slug="same",
            status=ArticleStatus.DRAFT,
            featured=False,
            allow_comments=True,
        )
        db.session.add(first)
        db.session.commit()
        assert unique_article_slug(pub.id, "Same") == "same-2"


def test_preview_and_filters(client, editor, app):
    _login(client)
    with app.app_context():
        pub = Publication(name="Main", slug="main-preview")
        db.session.add(pub)
        db.session.flush()
        article = Article(
            publication_id=pub.id,
            author_id=editor.id,
            title="Preview Me",
            slug="preview-me",
            status=ArticleStatus.DRAFT,
            content="Body",
            featured=False,
            allow_comments=True,
        )
        db.session.add(article)
        db.session.commit()
        article_id = article.id

    assert client.get(f"/admin/articles/{article_id}/preview").status_code == 200
    drafts = client.get("/admin/articles?status=DRAFT")
    assert drafts.status_code == 200
    assert b"Preview Me" in drafts.data
