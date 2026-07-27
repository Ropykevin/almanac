"""Add slug and body to projects for public detail pages.

Revision ID: 20260720_0016
Revises: 20260717_0015
Create Date: 2026-07-20
"""

from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "20260720_0016"
down_revision = "20260717_0015"
branch_labels = None
depends_on = None


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value).strip("-")
    return value or "project"


def upgrade() -> None:
    op.add_column("projects", sa.Column("slug", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("body", sa.Text(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, title FROM projects")).fetchall()
    used: set[str] = set()
    for row in rows:
        base = _slugify(row.title)
        candidate = base
        n = 2
        while candidate in used:
            candidate = f"{base}-{n}"
            n += 1
        used.add(candidate)
        conn.execute(
            sa.text("UPDATE projects SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": row.id},
        )

    op.alter_column("projects", "slug", nullable=False)
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=False)
    op.create_unique_constraint(
        "uq_projects_publication_slug",
        "projects",
        ["publication_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_projects_publication_slug", "projects", type_="unique")
    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.drop_column("projects", "body")
    op.drop_column("projects", "slug")
