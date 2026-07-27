"""Admin analytics dashboard."""

from __future__ import annotations

from flask import render_template, request
from flask_login import login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.services import analytics as analytics_service


@admin_bp.route("/analytics")
@login_required
@staff_required
def analytics_dashboard():
    try:
        days = int(request.args.get("days") or 30)
    except ValueError:
        days = 30
    snapshot = analytics_service.get_analytics_snapshot(days=days)

    chart_payload = {
        "views": {
            "labels": [p["date"] for p in snapshot.views_series],
            "values": [p["count"] for p in snapshot.views_series],
        },
        "subscribers": {
            "labels": [p["date"] for p in snapshot.subscriber_series],
            "values": [p["count"] for p in snapshot.subscriber_series],
        },
        "countries": {
            "labels": [c["country"] for c in snapshot.countries],
            "values": [c["views"] for c in snapshot.countries],
        },
        "reading": {
            "labels": [b["label"] for b in snapshot.reading_time["distribution"]],
            "values": [b["count"] for b in snapshot.reading_time["distribution"]],
        },
        "newsletter": {
            "labels": ["Sent", "Opened", "Clicked", "Failed"],
            "values": [
                snapshot.newsletter_summary["sent"],
                snapshot.newsletter_summary["opened"],
                snapshot.newsletter_summary["clicked"],
                snapshot.newsletter_summary["failed"],
            ],
        },
        "mostRead": {
            "labels": [a["title"][:42] for a in snapshot.most_read],
            "values": [a["views"] for a in snapshot.most_read],
        },
    }

    return render_template(
        "admin/analytics/dashboard.html",
        snapshot=snapshot,
        chart_payload=chart_payload,
        days=snapshot.days,
        breadcrumbs=[{"label": "Analytics", "url": None}],
        page_title="Analytics",
        active_nav="analytics",
    )
