"""Attach articles to research projects.

Revision ID: 20260814_0018
Revises: 20260813_0017
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_0018"
down_revision = "20260813_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_articles_project_id"),
        "articles",
        ["project_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_articles_project_id_projects",
        "articles",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_articles_project_id_projects", "articles", type_="foreignkey")
    op.drop_index(op.f("ix_articles_project_id"), table_name="articles")
    op.drop_column("articles", "project_id")
