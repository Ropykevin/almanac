"""Newsletter campaign tests."""

import uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import (
    Article,
    ArticleStatus,
    DeliveryStatus,
    Newsletter,
    NewsletterDelivery,
    NewsletterStatus,
    Publication,
    Subscriber,
    SubscriberStatus,
    User,
    UserRole,
)
from app.services import newsletters as newsletter_service
from app.utils.tokens import generate_click_token, generate_open_token


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def _seed_article_and_subscriber(app):
    with app.app_context():
        user = User.query.filter_by(email="editor@example.com").first()
        if user is None:
            user = User(
                email="editor@example.com",
                full_name="Editor",
                role=UserRole.EDITOR,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)
        publication = Publication.query.first()
        if publication is None:
            publication = Publication(name="Liminal", slug="liminal-nl")
            db.session.add(publication)
            db.session.flush()
        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title="Dispatch One",
            slug="dispatch-one",
            excerpt="A short excerpt.",
            content="<p>Full story body.</p>",
            status=ArticleStatus.PUBLISHED,
            featured=False,
            allow_comments=True,
            published_at=datetime.now(timezone.utc),
        )
        subscriber = Subscriber(
            publication_id=publication.id,
            email="reader@example.com",
            full_name="Reader",
            status=SubscriberStatus.ACTIVE,
            subscribed_at=datetime.now(timezone.utc),
        )
        db.session.add_all([article, subscriber])
        db.session.commit()
        return str(article.id)


def test_create_preview_and_send(client, editor, app):
    article_id = _seed_article_and_subscriber(app)
    _login(client)

    created = client.post(
        "/admin/newsletters/new",
        data={
            "subject": "Weekly dispatch",
            "article_id": article_id,
            "html_content": "",
            "submit": "Save campaign",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert b"Weekly dispatch" in created.data

    with app.app_context():
        newsletter = Newsletter.query.filter_by(subject="Weekly dispatch").one()
        newsletter_id = str(newsletter.id)

    preview = client.get(f"/admin/newsletters/{newsletter_id}/preview/html")
    assert preview.status_code == 200
    assert b"Dispatch One" in preview.data
    assert b"Read the full story" in preview.data

    sent = client.post(
        f"/admin/newsletters/{newsletter_id}/send",
        follow_redirects=True,
    )
    assert sent.status_code == 200
    assert b"Campaign sent" in sent.data

    with app.app_context():
        newsletter = Newsletter.query.filter_by(subject="Weekly dispatch").one()
        assert newsletter.status == NewsletterStatus.SENT
        delivery = NewsletterDelivery.query.filter_by(newsletter_id=newsletter.id).one()
        assert delivery.status == DeliveryStatus.SENT
        delivery_id = str(delivery.id)
        open_token = generate_open_token(delivery_id)
        click_token = generate_click_token(delivery_id, "https://example.com/story")

    pixel = client.get(f"/n/o/{open_token}")
    assert pixel.status_code == 200
    assert pixel.mimetype == "image/gif"

    with app.app_context():
        delivery = db.session.get(NewsletterDelivery, uuid.UUID(delivery_id))
        assert delivery is not None
        assert delivery.opened_at is not None
        assert delivery.status == DeliveryStatus.OPENED

    click = client.get(f"/n/c/{click_token}")
    assert click.status_code == 302
    assert click.headers["Location"] == "https://example.com/story"

    with app.app_context():
        delivery = db.session.get(NewsletterDelivery, uuid.UUID(delivery_id))
        assert delivery is not None
        assert delivery.clicked_at is not None
        assert delivery.status == DeliveryStatus.CLICKED
        stats = newsletter_service.delivery_stats(delivery.newsletter_id)
        assert stats["opened"] == 1
        assert stats["clicked"] == 1
        assert stats["sent"] == 1
        assert stats["delivered"] == 1


def test_schedule_and_process_due(client, editor, app):
    article_id = _seed_article_and_subscriber(app)
    _login(client)

    client.post(
        "/admin/newsletters/new",
        data={
            "subject": "Scheduled drop",
            "article_id": article_id,
            "html_content": "<p>Hello</p>",
            "submit": "Save campaign",
        },
    )
    with app.app_context():
        newsletter = Newsletter.query.filter_by(subject="Scheduled drop").one()
        newsletter.status = NewsletterStatus.SCHEDULED
        newsletter.scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

    listing = client.get("/admin/newsletters", follow_redirects=True)
    assert listing.status_code == 200

    with app.app_context():
        newsletter = Newsletter.query.filter_by(subject="Scheduled drop").one()
        assert newsletter.status == NewsletterStatus.SENT


def test_test_email_endpoint(client, editor, app):
    article_id = _seed_article_and_subscriber(app)
    _login(client)
    client.post(
        "/admin/newsletters/new",
        data={
            "subject": "Testable",
            "article_id": article_id,
            "html_content": "",
            "submit": "Save campaign",
        },
    )
    with app.app_context():
        newsletter_id = str(Newsletter.query.filter_by(subject="Testable").one().id)

    response = client.post(
        f"/admin/newsletters/{newsletter_id}/test",
        data={"email": "qa@example.com", "submit": "Send test"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Test email sent" in response.data
