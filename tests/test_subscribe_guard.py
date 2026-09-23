"""Subscribe anti-abuse guards."""

from app.forms.public import SubscribeForm
from app.utils.subscribe_guard import (
    evaluate_subscribe_request,
    honeypot_tripped,
    turnstile_enabled,
)


def test_honeypot_blocks_without_creating_subscriber(client, app):
    response = client.post(
        "/subscribe",
        data={
            "full_name": "Bot",
            "email": "bot@example.com",
            "company": "http://spam.example",
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
    form = SubscribeForm(meta={"csrf": False})
    form.email.data = "crawler@example.com"
    form.company.data = ""

    class FakeUA:
        string = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

    class FakeRequest:
        remote_addr = "127.0.0.1"
        user_agent = FakeUA()
        form = {}

    with app.app_context():
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(form, FakeRequest())
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
    response = client.post(
        "/subscribe",
        data={"email": "human@example.com", "submit": "Subscribe"},
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
    form = SubscribeForm(meta={"csrf": False})
    form.email.data = "ok@example.com"
    form.company.data = ""

    class FakeUA:
        string = "Mozilla/5.0"

    class FakeRequest:
        remote_addr = "127.0.0.1"
        user_agent = FakeUA()
        form = {}

    with app.app_context():
        app.config["TURNSTILE_SITE_KEY"] = ""
        app.config["TURNSTILE_SECRET_KEY"] = ""
        result = evaluate_subscribe_request(form, FakeRequest())
        assert result.ok
