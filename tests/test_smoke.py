"""Smoke tests for foundation + auth redirects."""


def test_index_ok(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Almanac Africa AI" in response.data


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_auth_login_page(client):
    assert client.get("/auth/login").status_code == 200


def test_admin_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in {302, 401}
    assert "/auth/login" in response.headers.get("Location", "")


def test_404(client):
    assert client.get("/does-not-exist").status_code == 404
