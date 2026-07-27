"""Media library tests."""

import io
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Media, User
from app.services import media as media_service


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
    # Minimal 1×1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_upload_preview_search_delete(client, editor, app):
    _login(client)

    upload = client.post(
        "/admin/media/upload",
        data={
            "file": (io.BytesIO(_png_bytes()), "hero-shot.png"),
            "alt_text": "Hero skyline",
            "submit": "Upload",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"hero-shot.png" in upload.data or b"Hero skyline" in upload.data

    with app.app_context():
        media = Media.query.filter_by(original_name="hero-shot.png").one()
        media_id = str(media.id)
        disk = Path(app.config["UPLOAD_FOLDER"]) / media.file_name
        assert disk.exists()

    listing = client.get("/admin/media?q=hero")
    assert listing.status_code == 200
    assert b"hero-shot.png" in listing.data

    detail = client.get(f"/admin/media/{media_id}")
    assert detail.status_code == 200
    assert b"Hero skyline" in detail.data

    pdf_upload = client.post(
        "/admin/media/upload",
        data={
            "file": (io.BytesIO(b"%PDF-1.4 test"), "brief.pdf"),
            "alt_text": "Briefing",
            "submit": "Upload",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert pdf_upload.status_code == 200

    pdfs = client.get("/admin/media?kind=pdf")
    assert b"brief.pdf" in pdfs.data

    deleted = client.post(
        f"/admin/media/{media_id}/delete",
        follow_redirects=True,
    )
    assert deleted.status_code == 200
    with app.app_context():
        assert db.session.get(Media, uuid.UUID(media_id)) is None
        assert not disk.exists()


def test_replace_keeps_id(client, editor, app):
    _login(client)
    client.post(
        "/admin/media/upload",
        data={
            "file": (io.BytesIO(_png_bytes()), "original.png"),
            "alt_text": "Original",
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    with app.app_context():
        media = Media.query.filter_by(original_name="original.png").one()
        media_id = media.id
        old_name = media.file_name

    client.post(
        f"/admin/media/{media_id}",
        data={
            "alt_text": "Replaced alt",
            "file": (io.BytesIO(_png_bytes()), "replacement.png"),
            "submit": "Save changes",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with app.app_context():
        media = db.session.get(Media, media_id)
        assert media is not None
        assert media.original_name == "replacement.png"
        assert media.alt_text == "Replaced alt"
        assert media.file_name != old_name
        assert (Path(app.config["UPLOAD_FOLDER"]) / media.file_name).exists()


def test_editor_upload_and_picker(client, editor, app):
    _login(client)
    response = client.post(
        "/admin/articles/editor/upload",
        data={"file": (io.BytesIO(_png_bytes()), "inline.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload and payload.get("location")
    assert "/static/uploads/" in payload["location"]

    picker = client.get("/admin/media/picker?kind=image")
    assert picker.status_code == 200
    assert b"Media library" in picker.data

    api = client.get("/admin/media/api?kind=image")
    assert api.status_code == 200
    body = api.get_json()
    assert body["total"] >= 1


def test_pagination(client, editor, app):
    _login(client)
    with app.app_context():
        user = User.query.filter_by(email="editor@example.com").one()
        for i in range(30):
            storage = FileStorage(
                stream=io.BytesIO(f"document {i}".encode()),
                filename=f"file-{i}.txt",
                content_type="text/plain",
            )
            media_service.save_upload(storage, user, alt_text=f"Doc {i}")
        db.session.commit()

    page1 = client.get("/admin/media?kind=document&page=1")
    assert page1.status_code == 200
    assert b"Page 1" in page1.data
    page2 = client.get("/admin/media?kind=document&page=2")
    assert page2.status_code == 200
    assert b"Page 2" in page2.data
