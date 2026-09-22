"""Public website tests."""

from datetime import datetime, timezone

from app.extensions import db
from app.models import Article, ArticleStatus, Publication, Subscriber, User, UserRole


def _seed_published(app, *, title="Public Story", slug="public-story", featured=False):
    with app.app_context():
        user = User(
            email="writer@example.com",
            full_name="Ada Writer",
            role=UserRole.EDITOR,
            is_active=True,
            email_verified=True,
            bio="Reports on African AI.",
        )
        user.set_password("password123")
        publication = Publication(name="Liminal", slug="liminal-public")
        db.session.add_all([user, publication])
        db.session.flush()
        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title=title,
            slug=slug,
            excerpt="A short excerpt for the public site.",
            content="<p>Full <strong>story</strong> body.</p>",
            status=ArticleStatus.PUBLISHED,
            featured=featured,
            allow_comments=True,
            reading_time=3,
            published_at=datetime.now(timezone.utc),
        )
        db.session.add(article)
        db.session.commit()
        return article.slug


def test_public_pages_ok(client):
    assert client.get("/").status_code == 200
    assert client.get("/archive").status_code == 200
    assert client.get("/about").status_code == 200
    assert client.get("/search").status_code == 200
    assert client.get("/subscribe").status_code == 200


def test_article_page_shows_reading_time_and_author(client, app):
    slug = _seed_published(app, featured=True)
    response = client.get(f"/article/{slug}")
    assert response.status_code == 200
    assert b"Public Story" in response.data
    assert b"3 min read" in response.data
    assert b"Ada Writer" in response.data
    assert b"Author" in response.data


def test_search_and_archive(client, app):
    _seed_published(app, title="Lagos Models", slug="lagos-models")
    search = client.get("/search?q=Lagos")
    assert search.status_code == 200
    assert b"Lagos Models" in search.data
    archive = client.get("/archive")
    assert b"Lagos Models" in archive.data


def test_subscribe(client, app):
    response = client.post(
        "/subscribe",
        data={
            "full_name": "Reader One",
            "email": "reader@example.com",
            "submit": "Subscribe",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"confirm" in response.data.lower()
    with app.app_context():
        sub = Subscriber.query.filter_by(email="reader@example.com").first()
        assert sub is not None
        assert sub.status.value == "PENDING"


def test_subscribe_mail_failure_does_not_500(client, app, monkeypatch):
    from app.utils import email as email_utils

    def boom(*_args, **_kwargs):
        raise email_utils.MailSendError(
            "The mail provider temporarily blocked outbound mail "
            "(unusual sending activity)."
        )

    monkeypatch.setattr(
        "app.services.subscribers.send_subscription_verification_email",
        boom,
    )
    response = client.post(
        "/subscribe",
        data={
            "full_name": "Reader Two",
            "email": "reader2@example.com",
            "submit": "Subscribe",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"could not send" in response.data.lower()
    with app.app_context():
        sub = Subscriber.query.filter_by(email="reader2@example.com").first()
        assert sub is not None
        assert sub.status.value == "PENDING"


def test_unpublished_not_public(client, app):
    with app.app_context():
        user = User(
            email="hidden@example.com",
            full_name="Hidden",
            role=UserRole.EDITOR,
            is_active=True,
        )
        user.set_password("password123")
        publication = Publication(name="X", slug="x-pub")
        db.session.add_all([user, publication])
        db.session.flush()
        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title="Draft Only",
            slug="draft-only",
            status=ArticleStatus.DRAFT,
            featured=False,
            allow_comments=True,
        )
        db.session.add(article)
        db.session.commit()

    assert client.get("/article/draft-only").status_code == 404
