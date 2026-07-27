"""Authentication routes: login, logout, forgot/reset password."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.extensions import db, limiter
from app.forms.auth import ForgotPasswordForm, LoginForm, ResetPasswordForm
from app.models import User
from app.utils.email import send_password_reset_email
from app.utils.tokens import generate_reset_token, verify_reset_token


def _safe_next_url(next_url: str | None) -> str | None:
    """Allow only relative same-site redirects."""
    if not next_url:
        return None
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return None
    if not next_url.startswith("/"):
        return None
    return next_url


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("Your account is inactive. Contact an administrator.", "error")
            return render_template("auth/login.html", form=form)

        user.touch_login()
        db.session.commit()
        login_user(user, remember=form.remember_me.data)
        flash(f"Welcome back, {user.full_name}.", "success")

        next_url = _safe_next_url(request.args.get("next"))
        return redirect(next_url or url_for("admin.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        # Always show the same message to avoid account enumeration.
        flash(
            "If an account exists for that email, a reset link has been sent.",
            "info",
        )
        if user and user.is_active:
            token = generate_reset_token(user.email)
            send_password_reset_email(user.email, token)
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    email = verify_reset_token(token)
    if email is None:
        flash("The password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if user is None or not user.is_active:
        flash("The password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated. You can sign in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
