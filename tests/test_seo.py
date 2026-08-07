"""SEO, sitemap, robots, RSS, and search tests."""

from datetime import datetime, timezone

from app.extensions import db
from app.models import Article, ArticleStatus, Publication, User, UserRole


def _seed_article(app, *, slug="seo-story", title="SEO Story", seo_title=None):
    with app.app_context():
        user = User(
            email="seo-author@example.com",
            full_name="SEO Author",
            role=UserRole.EDITOR,
            is_active=True,
        )
        user.set_password("password123")
        publication = Publication(name="Liminal SEO", slug="liminal-seo")
        db.session.add_all([user, publication])
        db.session.flush()
        article = Article(
            publication_id=publication.id,
            author_id=user.id,
            title=title,
            slug=slug,
            excerpt="A carefully written excerpt for search engines.",
            content="<p>Full body about Lagos models and African AI research.</p>",
            seo_title=seo_title or "Custom SEO Title",
            seo_description="Custom meta description for social sharing.",
            canonical_url=None,
            status=ArticleStatus.PUBLISHED,
            featured=False,
            allow_comments=True,
            reading_time=4,
            published_at=datetime.now(timezone.utc),
        )
        db.session.add(article)
        db.session.commit()
        return article.slug


def test_article_seo_tags(client, app):
    slug = _seed_article(app)
    response = client.get(f"/article/{slug}")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Custom SEO Title" in html
    assert "Custom meta description for social sharing." in html
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'name="twitter:card"' in html
    assert 'application/ld+json' in html
    assert "NewsArticle" in html
    assert 'rel="canonical"' in html
    assert f"/article/{slug}" in html


def test_sitemap_robots_rss(client, app):
    slug = _seed_article(app, slug="feed-story", title="Feed Story")
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert b"application/xml" in sitemap.content_type.encode() or sitemap.mimetype == "application/xml"
    assert b"/sitemap" not in sitemap.data or b"urlset" in sitemap.data
    assert f"/article/{slug}".encode() in sitemap.data
    assert b"/archive" in sitemap.data

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert b"Disallow: /admin/" in robots.data
    assert b"Sitemap:" in robots.data

    feed = client.get("/feed.xml")
    assert feed.status_code == 200
    assert b"<rss" in feed.data
    assert b"Feed Story" in feed.data
    assert client.get("/rss.xml").status_code == 200


def test_full_text_search(client, app):
    _seed_article(app, slug="lagos-models", title="Lagos Models")
    response = client.get("/search?q=Lagos")
    assert response.status_code == 200
    assert b"Lagos Models" in response.data
    # Multi-token ILIKE path (SQLite) / FTS path (Postgres)
    response2 = client.get("/search?q=African%20research")
    assert response2.status_code == 200
    assert b"Lagos Models" in response2.data


def test_google_site_verification_meta(client, app):
    app.config["GOOGLE_SITE_VERIFICATION"] = "test-google-token_123"
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    assert 'name="google-site-verification"' in html
    assert 'content="test-google-token_123"' in html
    assert "WebSite" in html
    assert "Organization" in html
    assert "Ideas, analysis, and insight on AI governance across Africa." in html


def test_homepage_has_canonical_and_sitemap_linked(client):
    home = client.get("/")
    assert home.status_code == 200
    assert b'rel="canonical"' in home.data

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert b"/sitemap.xml" in robots.data
