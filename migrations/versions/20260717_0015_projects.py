"""Add projects table for ongoing research tracking.

Revision ID: 20260717_0015
Revises: 20260716_0014
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260717_0015"
down_revision = "20260716_0014"
branch_labels = None
depends_on = None

project_status = postgresql.ENUM(
    "LIVE",
    "COMING_SOON",
    name="project_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "LIVE",
            "COMING_SOON",
            name="project_status",
        ).create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            project_status if bind.dialect.name == "postgresql" else sa.String(length=32),
            nullable=False,
            server_default="LIVE",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["publications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_publication_id"), "projects", ["publication_id"], unique=False)
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_publication_id"), table_name="projects")
    op.drop_table("projects")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="project_status").drop(bind, checkfirst=True)
