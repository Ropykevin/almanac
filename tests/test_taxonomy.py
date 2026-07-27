"""Category and tag management tests."""

from app.models import Article, Category, Tag


def _login(client):
    return client.post(
        "/auth/login",
        data={
            "email": "editor@example.com",
            "password": "password123",
            "submit": "Sign in",
        },
    )


def test_category_and_tag_crud(client, editor):
    _login(client)

    created = client.post(
        "/admin/categories/new",
        data={
            "name": "Artificial Intelligence",
            "slug": "",
            "description": "AI stories",
            "submit": "Save category",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert b"Artificial Intelligence" in created.data

    tag = client.post(
        "/admin/tags/new",
        data={"name": "Africa", "slug": "", "submit": "Save tag"},
        follow_redirects=True,
    )
    assert tag.status_code == 200
    assert b"Africa" in tag.data

    assert client.get("/admin/categories").status_code == 200
    assert client.get("/admin/tags").status_code == 200


def test_article_many_to_many_taxonomy(client, editor, app):
    _login(client)

    client.post(
        "/admin/categories/new",
        data={
            "name": "Policy",
            "slug": "policy",
            "submit": "Save category",
        },
    )
    client.post(
        "/admin/tags/new",
        data={"name": "Lagos", "slug": "lagos", "submit": "Save tag"},
    )

    with app.app_context():
        category = Category.query.filter_by(slug="policy").first()
        tag = Tag.query.filter_by(slug="lagos").first()
        assert category is not None
        assert tag is not None
        category_id = str(category.id)
        tag_id = str(tag.id)

    response = client.post(
        "/admin/articles/new",
        data={
            "title": "Taxonomy Story",
            "status": "DRAFT",
            "content": "<p>Body</p>",
            "categories": [category_id],
            "tags": [tag_id],
            "allow_comments": True,
            "submit": "Save article",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        article = Article.query.filter_by(slug="taxonomy-story").first()
        assert article is not None
        assert {c.slug for c in article.categories} == {"policy"}
        assert {t.slug for t in article.tags} == {"lagos"}
