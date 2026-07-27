"""Admin site settings routes."""

from __future__ import annotations

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.decorators import staff_required
from app.forms.settings import SiteSettingsForm
from app.services import site_settings as settings_service


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@staff_required
def site_settings():
    form = SiteSettingsForm()
    current = settings_service.get_site_settings()

    if form.validate_on_submit():
        try:
            current = settings_service.save_site_settings_from_form(
                form,
                uploader=current_user,
            )
        except settings_service.SettingsError as exc:
            flash(str(exc), "error")
        else:
            flash("Settings saved.", "success")
            return redirect(url_for("admin.site_settings"))

    if not form.is_submitted():
        form.site_name.data = current.name
        form.tagline.data = current.tagline
        form.description.data = current.description
        form.primary_color.data = current.primary_color
        form.home_welcome.data = current.home_welcome
        form.footer_blurb.data = current.footer_blurb
        form.footer_copyright.data = current.footer_copyright
        form.contact_email.data = current.contact_email
        form.contact_phone.data = current.contact_phone
        form.contact_address.data = current.contact_address
        form.social_twitter.data = current.social_twitter
        form.social_linkedin.data = current.social_linkedin
        form.social_facebook.data = current.social_facebook
        form.social_instagram.data = current.social_instagram
        form.social_youtube.data = current.social_youtube

    return render_template(
        "admin/settings/form.html",
        form=form,
        site=current,
        breadcrumbs=[{"label": "Settings", "url": None}],
        page_title="Site settings",
        active_nav="settings",
    )
