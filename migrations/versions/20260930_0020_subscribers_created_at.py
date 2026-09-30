"""Add created_at to subscribers for stale-pending purge.

Revision ID: 20260930_0020
Revises: 20260827_0019
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260930_0020"
down_revision = "20260827_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscribers",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("subscribers", "created_at")
