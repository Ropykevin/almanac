"""Pytest fixtures."""

import pytest

from app import create_app
from app.extensions import db
from app.models import User, UserRole


@pytest.fixture
def app(tmp_path):
    application = create_app("testing")
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def editor(app):
    user = User(
        email="editor@example.com",
        full_name="Editor User",
        role=UserRole.EDITOR,
        is_active=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user
