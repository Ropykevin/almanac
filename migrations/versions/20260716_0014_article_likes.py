"""Add article_likes table for public like engagement.

Revision ID: 20260716_0014
Revises: 20260716_0013
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260716_0014"
down_revision = "20260716_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_likes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "visitor_key",
            name="uq_article_likes_article_visitor",
        ),
    )
    op.create_index(
        op.f("ix_article_likes_article_id"),
        "article_likes",
        ["article_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_article_likes_article_id"), table_name="article_likes")
    op.drop_table("article_likes")
