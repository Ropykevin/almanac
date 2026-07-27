"""Flask CLI commands."""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User, UserRole


def register_cli(app: Flask) -> None:
    app.cli.add_command(create_user)
    app.cli.add_command(send_scheduled_newsletters)


@click.command("create-user")
@click.option("--email", prompt=True, help="User email address")
@click.option("--name", "full_name", prompt="Full name", help="Display name")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Password (min 8 characters)",
)
@click.option(
    "--role",
    type=click.Choice([r.value for r in UserRole], case_sensitive=False),
    default=UserRole.EDITOR.value,
    show_default=True,
    help="User role (SUPER_ADMIN, ADMIN, EDITOR)",
)
@with_appcontext
def create_user(email: str, full_name: str, password: str, role: str) -> None:
    """Create a user (Super Admin, Admin, or Editor)."""
    email = email.strip().lower()
    if len(password) < 8:
        raise click.ClickException("Password must be at least 8 characters.")

    if User.query.filter_by(email=email).first():
        raise click.ClickException(f"A user with email {email} already exists.")

    user = User(
        email=email,
        full_name=full_name.strip(),
        role=UserRole(role.upper()),
        is_active=True,
        email_verified=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created {user.role_label}: {user.email}")


@click.command("send-scheduled-newsletters")
@with_appcontext
def send_scheduled_newsletters() -> None:
    """Send newsletter campaigns whose schedule time has arrived."""
    from app.services import newsletters as newsletter_service

    count = newsletter_service.process_due_newsletters()
    click.echo(f"Processed {count} scheduled newsletter(s).")
