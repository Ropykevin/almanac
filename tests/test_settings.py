"""Site settings and security-related tests."""

import io

from app.extensions import db
from app.models import Publication, Setting
from app.services import site_settings as settings_service


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def _png_bytes():
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_settings_page_and_save(client, editor, app):
    _login(client)
    page = client.get("/admin/settings")
    assert page.status_code == 200
    assert b"Site settings" in page.data or b"Site & branding" in page.data

    saved = client.post(
        "/admin/settings",
        data={
            "site_name": "Liminal Test Press",
            "tagline": "Test · Tagline",
            "description": "About the test press",
            "primary_color": "#114433",
            "footer_blurb": "Footer copy for tests.",
            "footer_copyright": "© Test Press",
            "contact_email": "hello@example.com",
            "contact_phone": "+1 555 0100",
            "contact_address": "Lagos",
            "social_twitter": "https://x.com/liminal",
            "social_linkedin": "",
            "social_facebook": "",
            "social_instagram": "",
            "social_youtube": "",
            "logo_file": (io.BytesIO(_png_bytes()), "logo.png"),
            "submit": "Save settings",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert b"Settings saved" in saved.data

    with app.app_context():
        publication = Publication.query.first()
        assert publication.name == "Liminal Test Press"
        assert publication.primary_color == "#114433"
        assert publication.logo_id is not None
        assert Setting.query.filter_by(setting_key="contact_email").first().setting_value == (
            "hello@example.com"
        )

    home = client.get("/")
    assert b"Liminal Test Press" in home.data
    assert b"Footer copy for tests." in home.data
    assert b"hello@example.com" in home.data
    assert b"https://x.com/liminal" in home.data


def test_reject_spoofed_image_upload(client, editor, app):
    _login(client)
    response = client.post(
        "/admin/media/upload",
        data={
            "file": (io.BytesIO(b"not-an-image"), "evil.png"),
            "alt_text": "Bad",
            "submit": "Upload",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"not a valid PNG" in response.data.lower() or b"valid PNG" in response.data


def test_get_site_settings_defaults(app):
    with app.app_context():
        site = settings_service.get_site_settings()
        assert site.name
        assert site.primary_color.startswith("#")
        assert site.tagline
