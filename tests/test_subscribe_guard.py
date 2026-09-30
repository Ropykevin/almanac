"""Subscribe anti-abuse guards."""

from app.forms.public import SubscribeForm
from app.utils.subscribe_guard import (
    disposable_email,
    evaluate_subscribe_request,
    honeypot_tripped,
    issue_form_started_token,
    suspicious_email_local,
    turnstile_enabled,
)


def _valid_form(email: str = "ok@example.com", **extra) -> SubscribeForm:
    form = SubscribeForm(meta={"csrf": False})
    form.email.data = email
    form.company.data = extra.get("company", "")
    form.form_started.data = extra.get("form_started", issue_form_started_token())
    return form


def _fake_request(ua: str = "Mozilla/5.0", form_data: dict | None = None):
    payload = form_data or {}

    class FakeUA:
        string = ua

    class FakeRequest:
        remote_addr = "127.0.0.1"
        user_agent = FakeUA()
        form = payload

    return FakeRequest()


def test_honeypot_blocks_without_creating_subscriber(client, app):
    with app.app_context():
        token = issue_form_started_token()
    response = client.post(
        "/subscribe",
        data={
            "full_name": "Bot",
            "email": "bot@example.com",
            "company": "http://spam.example",
            "form_started": token,
            "submit": "Subscribe",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"confirm" in response.data.lower()
    with app.app_context():
        from app.models import Subscriber

        assert Subscriber.query.filter_by(email="bot@example.com").first() is None


def test_bot_user_agent_blocked(app):
    with app.app_context():
        form = _valid_form("crawler@example.com")
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(
            form,
            _fake_request(
                "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            ),
        )
        assert not result.ok
        assert result.reason == "bot_ua"
        assert result.silent


def test_turnstile_required_when_configured(client, app, monkeypatch):
    app.config["TURNSTILE_SITE_KEY"] = "site"
    app.config["TURNSTILE_SECRET_KEY"] = "secret"
    assert turnstile_enabled()

    monkeypatch.setattr(
        "app.utils.subscribe_guard.verify_turnstile",
        lambda *_a, **_k: False,
    )
    with app.app_context():
        token = issue_form_started_token()
    response = client.post(
        "/subscribe",
        data={
            "email": "human@example.com",
            "form_started": token,
            "submit": "Subscribe",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"confirm you are human" in response.data.lower()
    with app.app_context():
        from app.models import Subscriber

        assert Subscriber.query.filter_by(email="human@example.com").first() is None


def test_honeypot_helper_on_form(app):
    with app.app_context():
        form = SubscribeForm(meta={"csrf": False})
        form.company.data = ""
        assert not honeypot_tripped(form)
        form.company.data = "spam"
        assert honeypot_tripped(form)


def test_evaluate_ok_without_turnstile(app):
    with app.app_context():
        form = _valid_form()
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(form, _fake_request())
        assert result.ok


def test_missing_form_started_rejected(app):
    with app.app_context():
        form = _valid_form()
        form.form_started.data = ""
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(form, _fake_request())
        assert not result.ok
        assert result.reason == "form_timing"
        assert not result.silent


def test_form_too_fast_silent(app):
    with app.app_context():
        app.config["SUBSCRIBE_FORM_MIN_SECONDS"] = 30
        form = _valid_form()
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(form, _fake_request())
        assert not result.ok
        assert result.reason == "form_too_fast"
        assert result.silent


def test_disposable_and_suspicious_email(app):
    assert disposable_email("x@mailinator.com")
    assert disposable_email("x@foo.temp-mail.org")
    assert not disposable_email("person@gmail.com")
    assert suspicious_email_local("abcdefghijklmnopqrst@example.com")
    assert not suspicious_email_local("ada@example.com")

    with app.app_context():
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(
            _valid_form("spam@mailinator.com"),
            _fake_request(),
        )
        assert not result.ok
        assert result.reason == "disposable_email"
        assert result.silent

        result = evaluate_subscribe_request(
            _valid_form("abcdefghijklmnopqrst@example.com"),
            _fake_request(),
        )
        assert not result.ok
        assert result.reason == "suspicious_email"


def test_purge_stale_pending(app):
    from datetime import timedelta

    from app.extensions import db
    from app.models import Subscriber, SubscriberStatus
    from app.models.base import utcnow
    from app.services import subscribers as subscriber_service

    with app.app_context():
        sub = subscriber_service.create_subscriber_admin(
            email="stale@example.com",
            full_name="Stale",
            status=SubscriberStatus.PENDING,
        )
        sub.created_at = utcnow() - timedelta(days=10)
        db.session.commit()

        purged = subscriber_service.purge_stale_pending(older_than_days=7)
        assert purged == 1
        assert Subscriber.query.filter_by(email="stale@example.com").first() is None
