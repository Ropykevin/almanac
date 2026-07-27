"""Add PostgreSQL GIN index for article full-text search.

Revision ID: 20260716_0013
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260716_0013"
down_revision = "20260716_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_articles_search_fts
            ON articles
            USING GIN (
              to_tsvector(
                'english',
                coalesce(title, '') || ' ' ||
                coalesce(subtitle, '') || ' ' ||
                coalesce(excerpt, '') || ' ' ||
                coalesce(seo_title, '') || ' ' ||
                coalesce(seo_description, '') || ' ' ||
                coalesce(content, '')
              )
            )
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(sa.text("DROP INDEX IF EXISTS ix_articles_search_fts"))
