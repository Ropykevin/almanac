"""Project document upload tests."""

import io

from app.models import Project, ProjectDocument
from app.models.enums import ProjectStatus


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def test_project_document_upload_and_public_list(client, editor, app):
    _login(client)

    created = client.post(
        "/admin/projects/new",
        data={
            "title": "AI Infrastructure Map",
            "slug": "ai-infrastructure-map",
            "description": "Mapping compute and connectivity across Africa.",
            "body": "<p>Initial notes.</p>",
            "status": ProjectStatus.LIVE.value,
            "sort_order": 0,
            "is_published": "y",
            "submit": "Save project",
        },
        follow_redirects=False,
    )
    assert created.status_code == 302
    assert "/admin/projects/" in created.headers["Location"]
    assert created.headers["Location"].endswith("/edit")

    with app.app_context():
        project = Project.query.filter_by(slug="ai-infrastructure-map").one()
        project_id = str(project.id)

    upload = client.post(
        f"/admin/projects/{project_id}/documents",
        data={
            "file": (io.BytesIO(b"%PDF-1.4 project brief"), "briefing.pdf"),
            "title": "Project briefing",
            "submit": "Upload document",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"Project briefing" in upload.data
    assert b"Uploaded" in upload.data or b"briefing.pdf" in upload.data

    with app.app_context():
        assert ProjectDocument.query.count() == 1

    public = client.get("/projects/ai-infrastructure-map")
    assert public.status_code == 200
    assert b"Documents" in public.data
    assert b"Project briefing" in public.data
    assert b"Download" in public.data


def test_project_create_requires_login(client):
    response = client.get("/admin/projects/new", follow_redirects=False)
    assert response.status_code in {302, 401}
