"""Subscriber management tests."""

import io

from app.models import Subscriber, SubscriberStatus
from app.services import subscribers as subscriber_service
from app.utils.tokens import generate_unsubscribe_token


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def test_subscribe_verify_unsubscribe_flow(client, app):
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
        sub = Subscriber.query.filter_by(email="reader@example.com").one()
        assert sub.status == SubscriberStatus.PENDING
        token = sub.verification_token
        assert token

    verified = client.get(f"/subscribe/verify/{token}", follow_redirects=True)
    assert verified.status_code == 200
    assert b"confirmed" in verified.data.lower() or b"welcome" in verified.data.lower()

    with app.app_context():
        sub = Subscriber.query.filter_by(email="reader@example.com").one()
        assert sub.status == SubscriberStatus.ACTIVE
        assert sub.verification_token is None
        unsub_token = generate_unsubscribe_token(
            "reader@example.com",
            str(sub.publication_id),
        )

    gone = client.get(f"/unsubscribe/{unsub_token}", follow_redirects=True)
    assert gone.status_code == 200

    with app.app_context():
        sub = Subscriber.query.filter_by(email="reader@example.com").one()
        assert sub.status == SubscriberStatus.UNSUBSCRIBED


def test_duplicate_subscribe_stays_single_row(client, app):
    client.post(
        "/subscribe",
        data={"email": "dup@example.com", "full_name": "A", "submit": "Subscribe"},
    )
    client.post(
        "/subscribe",
        data={"email": "dup@example.com", "full_name": "B", "submit": "Subscribe"},
        follow_redirects=True,
    )
    with app.app_context():
        rows = Subscriber.query.filter_by(email="dup@example.com").all()
        assert len(rows) == 1
        assert rows[0].status == SubscriberStatus.PENDING


def test_admin_list_and_csv(client, editor, app):
    _login(client)
    with app.app_context():
        subscriber_service.create_subscriber_admin(
            email="active@example.com",
            full_name="Active Reader",
            status=SubscriberStatus.ACTIVE,
        )

    listing = client.get("/admin/subscribers")
    assert listing.status_code == 200
    assert b"active@example.com" in listing.data

    export = client.get("/admin/subscribers/export")
    assert export.status_code == 200
    assert export.mimetype == "text/csv"
    assert b"active@example.com" in export.data

    csv_bytes = (
        b"email,full_name,status\n"
        b"import@example.com,Imported,ACTIVE\n"
        b"active@example.com,Updated Name,ACTIVE\n"
    )
    imported = client.post(
        "/admin/subscribers/import",
        data={
            "file": (io.BytesIO(csv_bytes), "subs.csv"),
            "submit": "Import CSV",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert imported.status_code == 200
    assert b"created" in imported.data.lower() or b"Import complete" in imported.data

    with app.app_context():
        imported_row = Subscriber.query.filter_by(email="import@example.com").one()
        assert imported_row.status == SubscriberStatus.ACTIVE
        updated = Subscriber.query.filter_by(email="active@example.com").one()
        assert updated.full_name == "Updated Name"


def test_admin_rejects_duplicate_create(client, editor, app):
    _login(client)
    client.post(
        "/admin/subscribers/new",
        data={
            "email": "once@example.com",
            "full_name": "One",
            "status": "ACTIVE",
            "submit": "Save subscriber",
        },
    )
    again = client.post(
        "/admin/subscribers/new",
        data={
            "email": "once@example.com",
            "full_name": "Two",
            "status": "PENDING",
            "submit": "Save subscriber",
        },
        follow_redirects=True,
    )
    assert b"already exists" in again.data
    with app.app_context():
        assert Subscriber.query.filter_by(email="once@example.com").count() == 1


def test_admin_resend_all_pending(client, editor, app, monkeypatch):
    sent: list[str] = []

    def fake_send(email: str, token: str) -> None:
        sent.append(email)

    monkeypatch.setattr(
        "app.services.subscribers.send_subscription_verification_email",
        fake_send,
    )
    monkeypatch.setattr("app.services.subscribers.time.sleep", lambda *_a, **_k: None)

    _login(client)
    with app.app_context():
        subscriber_service.create_subscriber_admin(
            email="p1@example.com",
            full_name="P1",
            status=SubscriberStatus.PENDING,
        )
        subscriber_service.create_subscriber_admin(
            email="p2@example.com",
            full_name="P2",
            status=SubscriberStatus.PENDING,
        )
        subscriber_service.create_subscriber_admin(
            email="active@example.com",
            full_name="Active",
            status=SubscriberStatus.ACTIVE,
        )

    response = client.post(
        "/admin/subscribers/resend-pending",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Resent confirmation" in response.data
    assert sorted(sent) == ["p1@example.com", "p2@example.com"]
