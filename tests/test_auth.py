"""Authentication flow tests."""

from app.extensions import db
from app.models import User, UserRole
from app.utils.tokens import generate_reset_token


def test_login_success(client, editor):
    response = client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "remember_me": True,
            "submit": "Sign in",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Editor User" in response.data


def test_login_invalid_password(client, editor):
    response = client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "wrong-password",
            "submit": "Sign in",
        },
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_dashboard_after_login(client, editor):
    client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Editor" in response.data


def test_logout(client, editor):
    client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )
    response = client.post("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"logged out" in response.data.lower()
    assert client.get("/admin/").status_code in {302, 401}


def test_forgot_password_always_generic(client, editor):
    response = client.post(
        "/auth/forgot-password",
        data={"email": "editor@example.com", "submit": "Send reset link"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"If an account exists" in response.data


def test_reset_password(client, app, editor):
    with app.app_context():
        token = generate_reset_token(editor.email)

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": "newpassword99",
            "confirm_password": "newpassword99",
            "submit": "Update password",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"password has been updated" in response.data.lower()

    with app.app_context():
        user = db.session.get(User, editor.id)
        assert user.check_password("newpassword99")


def test_inactive_user_cannot_login(client, app):
    with app.app_context():
        user = User(
            email="inactive@example.com",
            full_name="Inactive",
            role=UserRole.ADMIN,
            is_active=False,
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "inactive@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )
    assert response.status_code == 200
    assert b"inactive" in response.data.lower()
