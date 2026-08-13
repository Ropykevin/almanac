"""Add project_documents table for project file attachments.

Revision ID: 20260813_0017
Revises: 20260720_0016
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260813_0017"
down_revision = "20260720_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_documents_media_id"),
        "project_documents",
        ["media_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_documents_project_id"),
        "project_documents",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_documents_project_id"), table_name="project_documents")
    op.drop_index(op.f("ix_project_documents_media_id"), table_name="project_documents")
    op.drop_table("project_documents")
