"""Public-facing publication website."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from email.utils import format_datetime

from flask import (
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from app.blueprints.main import main_bp
from app.extensions import limiter
from app.forms.public import CommentForm, SubscribeForm
from app.services import engagement as engagement_service
from app.services import public as public_service
from app.services import seo as seo_service
from app.services import subscribers as subscriber_service


@main_bp.route("/")
def index():
    """Premium publication home."""
    current_app.logger.debug("Serving main.index")
    from app.services import projects as project_service

    seo = seo_service.default_seo_context(
        title=current_app.config.get("APP_NAME"),
        description=seo_service.DEFAULT_META_DESCRIPTION,
        include_website_json_ld=True,
    )
    seo["page_title"] = current_app.config.get("APP_NAME")
    return render_template(
        "main/index.html",
        subscribe_form=SubscribeForm(),
        projects=project_service.list_published_projects(limit=3),
        tracking_show_all_link=True,
        tracking_always=True,
        active_nav="home",
        seo=seo,
    )


@main_bp.route("/blog")
@main_bp.route("/archive")
def archive():
    category = (request.args.get("category") or "").strip() or None
    tag = (request.args.get("tag") or "").strip() or None
    query = (request.args.get("q") or "").strip() or None
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    per_page = 12
    offset = (page - 1) * per_page

    articles = public_service.list_published_articles(
        limit=per_page,
        offset=offset,
        category_slug=category,
        tag_slug=tag,
        query=query,
    )
    total = public_service.count_published_articles(
        category_slug=category,
        tag_slug=tag,
        query=query,
    )
    categories = public_service.list_public_categories()
    total_pages = max((total + per_page - 1) // per_page, 1)
    title = f"Blog — “{query}”" if query else "Blog"

    return render_template(
        "main/archive.html",
        articles=articles,
        categories=categories,
        current_category=category,
        current_tag=tag,
        current_query=query or "",
        page=page,
        total_pages=total_pages,
        total=total,
        active_nav="archive",
        seo=seo_service.default_seo_context(
            title=title,
            description="Browse published stories from the blog.",
            path_endpoint="main.archive",
        ),
    )


@main_bp.route("/article/<slug>")
def article_detail(slug: str):
    article = public_service.get_published_article(slug)
    if article is None:
        abort(404)
    from app.services import analytics as analytics_service

    analytics_service.record_article_view(article, request)
    related = public_service.related_articles(article, limit=3)
    visitor_key = (request.cookies.get(engagement_service.VISITOR_COOKIE) or "").strip()
    mint_cookie = not visitor_key
    if mint_cookie:
        visitor_key = secrets.token_urlsafe(24)[:64]
    likes = engagement_service.like_state(article.id, visitor_key)
    comments = (
        engagement_service.list_approved_comments(article.id)
        if article.allow_comments
        else []
    )
    comment_form = CommentForm()
    response = make_response(
        render_template(
            "main/article.html",
            article=article,
            related=related,
            comments=comments,
            comment_form=comment_form,
            like_count=likes.count,
            liked=likes.liked,
            active_nav="archive",
            seo=seo_service.article_seo_context(article),
        )
    )
    if mint_cookie:
        response.set_cookie(
            engagement_service.VISITOR_COOKIE,
            visitor_key,
            max_age=60 * 60 * 24 * 365 * 2,
            httponly=True,
            samesite="Lax",
            secure=bool(request.is_secure),
        )
    return response


@main_bp.route("/article/<slug>/comments", methods=["POST"])
@limiter.limit("8 per minute")
def article_comment(slug: str):
    article = public_service.get_published_article(slug)
    if article is None:
        abort(404)
    form = CommentForm()
    if form.validate_on_submit():
        try:
            engagement_service.submit_comment(
                article,
                full_name=form.full_name.data,
                email=form.email.data,
                body=form.body.data,
            )
        except engagement_service.EngagementError as exc:
            flash(str(exc), "error")
        else:
            flash(
                "Thanks — your comment was submitted and will appear after review.",
                "success",
            )
    else:
        flash("Please check your comment details and try again.", "error")
    return redirect(url_for("main.article_detail", slug=slug) + "#comments")


@main_bp.route("/article/<slug>/like", methods=["POST"])
@limiter.limit("30 per minute")
def article_like(slug: str):
    article = public_service.get_published_article(slug)
    if article is None:
        abort(404)

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or (request.accept_mimetypes["application/json"]
            >= request.accept_mimetypes["text/html"])
    )

    # Prefer existing cookie; otherwise mint one key used for both like + Set-Cookie.
    visitor_key = (request.cookies.get(engagement_service.VISITOR_COOKIE) or "").strip()
    mint_cookie = not visitor_key
    if mint_cookie:
        visitor_key = secrets.token_urlsafe(24)[:64]

    try:
        state = engagement_service.toggle_like(article, visitor_key)
    except engagement_service.EngagementError as exc:
        if wants_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("main.article_detail", slug=slug))

    if wants_json:
        payload = jsonify({"ok": True, "liked": state.liked, "count": state.count})
    else:
        flash("Thanks for the signal." if state.liked else "Like removed.", "success")
        payload = redirect(url_for("main.article_detail", slug=slug) + "#engage")

    if mint_cookie:
        payload.set_cookie(
            engagement_service.VISITOR_COOKIE,
            visitor_key,
            max_age=60 * 60 * 24 * 365 * 2,
            httponly=True,
            samesite="Lax",
            secure=bool(request.is_secure),
        )
    return payload


@main_bp.route("/about")
def about():
    return render_template(
        "main/about.html",
        active_nav="about",
        seo=seo_service.default_seo_context(
            title="About",
            description="About the publication — African AI reported with clarity.",
            path_endpoint="main.about",
        ),
    )


@main_bp.route("/projects")
def projects():
    from app.services import projects as project_service

    return render_template(
        "main/projects.html",
        projects=project_service.list_published_projects_ordered(),
        active_nav="projects",
        seo=seo_service.default_seo_context(
            title="Projects — Ongoing research",
            description="Inquiries into African AI governance, infrastructure and AI in society across Africa.",
            path_endpoint="main.projects",
        ),
    )


@main_bp.route("/projects/<slug>")
def project_detail(slug: str):
    from app.services import projects as project_service
    from app.services.media import media_kind, media_public_url
    from app.utils.html_sanitize import sanitize_article_html

    project = project_service.get_published_project_by_slug(slug)
    if project is None:
        abort(404)

    documents = []
    for document in project_service.list_project_documents(project):
        media = document.media
        if media is None:
            continue
        documents.append(
            {
                "title": document.display_title,
                "url": media_public_url(media),
                "kind": media_kind(media),
                "size_label": project_service.format_file_size(media.size),
            }
        )

    return render_template(
        "main/project_detail.html",
        project=project,
        project_body_html=sanitize_article_html(project.body),
        project_documents=documents,
        active_nav="projects",
        seo=seo_service.default_seo_context(
            title=project.title,
            description=project.description[:300],
            path_endpoint="main.project_detail",
            slug=project.slug,
        ),
    )


@main_bp.route("/search")
def search():
    query = (request.args.get("q") or "").strip()
    results = public_service.search_articles(query) if query else []
    title = f"Search results for “{query}”" if query else "Search"
    return render_template(
        "main/search.html",
        query=query,
        results=results,
        active_nav="search",
        seo=seo_service.default_seo_context(
            title=title,
            description="Search published articles.",
            path_endpoint="main.search",
        ),
    )


@main_bp.route("/subscribe", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def subscribe():
    form = SubscribeForm()
    if form.validate_on_submit():
        _, outcome = subscriber_service.subscribe_email(
            email=form.email.data,
            full_name=form.full_name.data,
        )
        messages = {
            "created": (
                "success",
                "Check your email to confirm your subscription.",
            ),
            "pending_resent": (
                "info",
                "You’re almost there — we sent another confirmation email.",
            ),
            "unsubscribed_resent": (
                "info",
                "Welcome back. Confirm via email to reactivate your subscription.",
            ),
            "already_active": (
                "info",
                "You’re already subscribed. Thanks for staying with us.",
            ),
        }
        category, text = messages.get(
            outcome,
            ("info", "If that email can be subscribed, a confirmation was sent."),
        )
        flash(text, category)
        return redirect(url_for("main.subscribe"))

    from app.services import newsletters as newsletter_service
    from app.services import site_settings as site_settings_service
    from app.services import substack as substack_service

    site = site_settings_service.get_site_settings()
    substack_url = site.substack_archive_url if site else None
    substack_posts = (
        substack_service.fetch_recent_posts(substack_url, limit=12) if substack_url else []
    )

    return render_template(
        "main/subscribe.html",
        form=form,
        previous_newsletters=newsletter_service.list_sent_newsletters(limit=12),
        substack_url=substack_url,
        substack_posts=substack_posts,
        active_nav="subscribe",
        seo=seo_service.default_seo_context(
            title="Subscribe",
            description="Subscribe to get full access to the latest Newsletter.",
            path_endpoint="main.subscribe",
        ),
    )


@main_bp.route("/newsletter/<newsletter_id>")
def newsletter_detail(newsletter_id: str):
    """Public view of a previously sent newsletter."""
    import uuid

    from app.services import newsletters as newsletter_service

    try:
        nid = uuid.UUID(newsletter_id)
    except (TypeError, ValueError):
        abort(404)
    newsletter = newsletter_service.get_sent_newsletter(nid)
    if newsletter is None:
        abort(404)
    if (
        newsletter.article is not None
        and newsletter.article.status.value == "PUBLISHED"
    ):
        return redirect(
            url_for("main.article_detail", slug=newsletter.article.slug)
        )
    from app.utils.html_sanitize import sanitize_article_html

    return render_template(
        "main/newsletter_detail.html",
        newsletter=newsletter,
        newsletter_body_html=sanitize_article_html(newsletter.html_content),
        active_nav="subscribe",
        seo=seo_service.default_seo_context(
            title=newsletter.subject,
            description="Previously sent newsletter from Africa’s AI Almanac.",
            path_endpoint="main.newsletter_detail",
            newsletter_id=str(newsletter.id),
        ),
    )


@main_bp.route("/subscribe/verify/<token>")
def verify_subscription(token: str):
    subscriber = subscriber_service.verify_subscription(token)
    if subscriber is None:
        flash("That confirmation link is invalid or has already been used.", "error")
        return redirect(url_for("main.subscribe"))
    flash("Subscription confirmed. Welcome to Africa’s AI Almanac.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/unsubscribe", methods=["GET", "POST"])
@main_bp.route("/unsubscribe/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def unsubscribe(token: str | None = None):
    from app.forms.subscribers import UnsubscribeForm

    form = UnsubscribeForm()
    if token and request.method == "GET":
        subscriber = subscriber_service.unsubscribe_by_token(token)
        if subscriber is None:
            flash("That unsubscribe link is invalid or expired.", "error")
        else:
            flash("You have been unsubscribed.", "info")
        return redirect(url_for("main.index"))

    if form.validate_on_submit():
        subscriber = subscriber_service.unsubscribe_by_email(form.email.data)
        if subscriber is None:
            flash("We couldn’t find an active subscription for that email.", "warning")
        else:
            flash("You have been unsubscribed.", "info")
        return redirect(url_for("main.unsubscribe"))

    return render_template(
        "main/unsubscribe.html",
        form=form,
        active_nav="subscribe",
    )


@main_bp.route("/n/o/<token>")
def newsletter_open(token: str):
    """1×1 tracking pixel for newsletter opens."""
    import base64
    import uuid

    from flask import Response

    from app.services import newsletters as newsletter_service
    from app.utils.tokens import verify_open_token

    delivery_id = verify_open_token(token)
    if delivery_id:
        try:
            newsletter_service.record_open(uuid.UUID(delivery_id))
        except (TypeError, ValueError):
            pass

    pixel = base64.b64decode(
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    )
    return Response(pixel, mimetype="image/gif")


@main_bp.route("/n/c/<token>")
def newsletter_click(token: str):
    """Click redirect with engagement tracking."""
    import uuid

    from app.services import newsletters as newsletter_service
    from app.utils.tokens import verify_click_token

    payload = verify_click_token(token)
    if payload is None:
        flash("That link is invalid or expired.", "error")
        return redirect(url_for("main.index"))
    try:
        redirect_url = newsletter_service.record_click(
            uuid.UUID(payload["delivery_id"]),
            payload["url"],
        )
    except (TypeError, ValueError):
        redirect_url = None
    if not redirect_url:
        flash("That link is invalid.", "error")
        return redirect(url_for("main.index"))
    return redirect(redirect_url)


@main_bp.route("/sitemap.xml")
def sitemap():
    urls = [
        {
            "loc": url_for("main.index", _external=True),
            "changefreq": "daily",
            "priority": "1.0",
            "lastmod": None,
        },
        {
            "loc": url_for("main.archive", _external=True),
            "changefreq": "daily",
            "priority": "0.8",
            "lastmod": None,
        },
        {
            "loc": url_for("main.about", _external=True),
            "changefreq": "monthly",
            "priority": "0.5",
            "lastmod": None,
        },
        {
            "loc": url_for("main.projects", _external=True),
            "changefreq": "weekly",
            "priority": "0.6",
            "lastmod": None,
        },
        {
            "loc": url_for("main.subscribe", _external=True),
            "changefreq": "monthly",
            "priority": "0.4",
            "lastmod": None,
        },
        {
            "loc": url_for("main.search", _external=True),
            "changefreq": "weekly",
            "priority": "0.3",
            "lastmod": None,
        },
    ]
    for article in public_service.list_sitemap_articles():
        lastmod = article.updated_at or article.published_at or article.created_at
        urls.append(
            {
                "loc": url_for("main.article_detail", slug=article.slug, _external=True),
                "lastmod": lastmod.date().isoformat() if lastmod else None,
                "changefreq": "weekly",
                "priority": "0.7",
            }
        )
    from app.services import projects as project_service

    for project in project_service.list_published_projects_ordered():
        lastmod = project.updated_at or project.created_at
        urls.append(
            {
                "loc": url_for(
                    "main.project_detail",
                    slug=project.slug,
                    _external=True,
                ),
                "lastmod": lastmod.date().isoformat() if lastmod else None,
                "changefreq": "weekly",
                "priority": "0.5",
            }
        )
    xml = render_template("main/sitemap.xml", urls=urls)
    return Response(xml, mimetype="application/xml")


@main_bp.route("/robots.txt")
def robots():
    body = render_template(
        "main/robots.txt",
        sitemap_url=url_for("main.sitemap", _external=True),
    )
    return Response(body, mimetype="text/plain")


@main_bp.route("/feed.xml")
@main_bp.route("/rss.xml")
def rss_feed():
    articles = public_service.list_feed_articles(limit=40)
    items = []
    for article in articles:
        published = article.published_at or article.created_at
        if published and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        description = seo_service.article_description(article)
        content = (article.content or "").replace("]]>", "]]]]><![CDATA[>")
        items.append(
            {
                "title": article.title,
                "link": url_for(
                    "main.article_detail",
                    slug=article.slug,
                    _external=True,
                ),
                "pub_date": format_datetime(published) if published else None,
                "author": article.author.full_name if article.author else None,
                "description": description,
                "content": content,
            }
        )
    last_build = datetime.now(timezone.utc)
    if items and articles and (articles[0].published_at or articles[0].updated_at):
        last_build = articles[0].published_at or articles[0].updated_at
        if last_build.tzinfo is None:
            last_build = last_build.replace(tzinfo=timezone.utc)
    xml = render_template(
        "main/rss.xml",
        site_url=url_for("main.index", _external=True),
        feed_url=url_for("main.rss_feed", _external=True),
        site_description=(
            "African intelligence, reported with clarity — "
            "stories at the edge of technology, culture, and power."
        ),
        last_build=format_datetime(last_build),
        items=items,
    )
    return Response(xml, mimetype="application/rss+xml")


@main_bp.route("/health")
def health():
    """Simple health check for orchestration / load balancers."""
    return {"status": "ok", "service": current_app.config.get("APP_NAME")}, 200
