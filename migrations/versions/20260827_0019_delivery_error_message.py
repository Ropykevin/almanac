"""Store newsletter delivery failure messages for admin debugging.

Revision ID: 20260827_0019
Revises: 20260814_0018
Create Date: 2026-08-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260827_0019"
down_revision = "20260814_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "newsletter_deliveries",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("newsletter_deliveries", "error_message")
