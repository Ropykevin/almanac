"""Admin dashboard — authenticated staff only."""

from __future__ import annotations

from flask import current_app, flash, render_template
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.services.dashboard import DashboardStats, get_dashboard_stats, get_recent_activity


def _empty_stats() -> DashboardStats:
    return DashboardStats(
        total_articles=0,
        draft_articles=0,
        published_articles=0,
        subscribers=0,
        newsletter_campaigns=0,
    )


@admin_bp.route("/")
@login_required
@staff_required
def dashboard():
    """Staff dashboard with publishing metrics and recent activity."""
    try:
        stats = get_dashboard_stats()
        recent_activity = get_recent_activity(limit=10)
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.exception("Dashboard metrics unavailable: %s", exc)
        flash(
            "Dashboard data could not be loaded. Check the database connection and run migrations.",
            "warning",
        )
        stats = _empty_stats()
        recent_activity = []
    except SQLAlchemyError as exc:
        current_app.logger.exception("Unexpected dashboard query error: %s", exc)
        flash("Dashboard data could not be loaded right now.", "error")
        stats = _empty_stats()
        recent_activity = []

    breadcrumbs = [{"label": "Dashboard", "url": None}]
    return render_template(
        "admin/dashboard.html",
        user=current_user,
        stats=stats,
        recent_activity=recent_activity,
        breadcrumbs=breadcrumbs,
        page_title="Dashboard",
        active_nav="dashboard",
    )
