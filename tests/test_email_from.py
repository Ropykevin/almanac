"""Outbound From header uses the publication / app display name."""


def test_format_from_header_uses_site_or_app_name(app):
    from email.utils import parseaddr

    from app.utils.email import format_from_header

    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "hello@almanac.africa"
        app.config["APP_NAME"] = "Africa's AI Almanac"
        name, address = parseaddr(format_from_header())
        assert address == "hello@almanac.africa"
        assert name
        assert "@" not in name


def test_format_from_header_keeps_mailbox_when_env_has_name(app):
    from email.utils import parseaddr

    from app.utils.email import format_from_header

    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "Ignored <hello@almanac.africa>"
        app.config["APP_NAME"] = "Africa's AI Almanac"
        name, address = parseaddr(format_from_header())
        assert address == "hello@almanac.africa"
        assert name
        assert name != "Ignored"
