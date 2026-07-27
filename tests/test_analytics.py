"""Analytics dashboard and view tracking tests."""

from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    Article,
    ArticleStatus,
    ArticleView,
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
from app.services import analytics as analytics_service


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def _seed_public_article(app, *, slug="analytics-story", title="Analytics Story"):
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
            publication = Publication(name="Liminal", slug="liminal-analytics")
            db.session.add(publication)
            db.session.flush()
        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title=title,
            slug=slug,
            excerpt="Excerpt",
            content="<p>Body copy for analytics testing.</p>",
            status=ArticleStatus.PUBLISHED,
            featured=False,
            allow_comments=True,
            reading_time=5,
            published_at=datetime.now(timezone.utc),
        )
        db.session.add(article)
        db.session.commit()
        return article.slug


def test_public_article_records_view(client, app):
    slug = _seed_public_article(app)
    response = client.get(
        f"/article/{slug}",
        headers={
            "User-Agent": "Mozilla/5.0 Chrome/120.0",
            "CF-IPCountry": "NG",
        },
    )
    assert response.status_code == 200
    with app.app_context():
        view = ArticleView.query.one()
        assert view.country == "Nigeria"
        assert view.browser == "Chrome"


def test_staff_view_not_recorded(client, editor, app):
    slug = _seed_public_article(app)
    _login(client)
    assert client.get(f"/article/{slug}").status_code == 200
    with app.app_context():
        assert ArticleView.query.count() == 0


def test_analytics_dashboard(client, editor, app):
    slug = _seed_public_article(app, slug="top-read", title="Top Read Piece")
    # Anonymous view
    client.get(
        f"/article/{slug}",
        headers={"User-Agent": "Mozilla/5.0 Firefox/121.0", "CF-IPCountry": "KE"},
    )

    with app.app_context():
        publication = Publication.query.first()
        subscriber = Subscriber(
            publication_id=publication.id,
            email="growth@example.com",
            status=SubscriberStatus.ACTIVE,
            subscribed_at=datetime.now(timezone.utc),
        )
        newsletter = Newsletter(
            publication_id=publication.id,
            subject="Analytics Campaign",
            status=NewsletterStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        db.session.add_all([subscriber, newsletter])
        db.session.flush()
        delivery = NewsletterDelivery(
            newsletter_id=newsletter.id,
            subscriber_id=subscriber.id,
            status=DeliveryStatus.OPENED,
            sent_at=datetime.now(timezone.utc),
            opened_at=datetime.now(timezone.utc),
        )
        db.session.add(delivery)
        db.session.commit()

    _login(client)
    page = client.get("/admin/analytics?days=30")
    assert page.status_code == 200
    assert b"Article views" in page.data
    assert b"Subscriber growth" in page.data
    assert b"Newsletter performance" in page.data
    assert b"Most read articles" in page.data
    assert b"Countries" in page.data
    assert b"Reading time" in page.data
    assert b"Top Read Piece" in page.data
    assert b"Analytics Campaign" in page.data
    assert b"chart-views" in page.data

    with app.app_context():
        snapshot = analytics_service.get_analytics_snapshot(days=30)
        assert snapshot.total_views >= 1
        assert snapshot.most_read
        assert snapshot.countries
        assert snapshot.newsletter_summary["opened"] >= 1
        assert snapshot.reading_time["average"] > 0
