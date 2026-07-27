"""Admin dashboard tests."""

from app.extensions import db
from app.models import ActivityLog, Article, ArticleStatus, Publication, UserRole


def test_dashboard_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in {302, 401}
    assert "/auth/login" in response.headers.get("Location", "")


def test_dashboard_renders_stats(client, editor, app):
    with app.app_context():
        publication = Publication(name="Weekly", slug="weekly")
        db.session.add(publication)
        db.session.flush()

        article = Article(
            publication_id=publication.id,
            author_id=editor.id,
            title="Draft piece",
            slug="draft-piece",
            status=ArticleStatus.DRAFT,
            featured=False,
            allow_comments=True,
        )
        published = Article(
            publication_id=publication.id,
            author_id=editor.id,
            title="Live piece",
            slug="live-piece",
            status=ArticleStatus.PUBLISHED,
            featured=False,
            allow_comments=True,
        )
        activity = ActivityLog(
            user_id=editor.id,
            action="article.created",
            description="Created draft piece",
        )
        db.session.add_all([article, published, activity])
        db.session.commit()

    client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Total Articles" in response.data
    assert b"Draft Articles" in response.data
    assert b"Published Articles" in response.data
    assert b"Subscribers" in response.data
    assert b"Newsletter Campaigns" in response.data
    assert b"Recent Activity" in response.data
    assert b"article.created" in response.data
    assert b"Admin console" in response.data
