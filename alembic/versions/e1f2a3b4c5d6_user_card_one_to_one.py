"""Enforce one-to-one user-card: drop is_default/is_active, add unique constraint on user_id

Revision ID: e1f2a3b4c5d6
Revises: d7e2f3a4b5c6
Create Date: 2026-08-28 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d7e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep only the latest card per user; delete older duplicates before adding constraint
    op.execute("""
        DELETE FROM user_cards
        WHERE id NOT IN (
            SELECT DISTINCT ON (user_id) id
            FROM user_cards
            ORDER BY user_id, created_at DESC
        )
    """)

    op.drop_column("user_cards", "is_default")
    op.drop_column("user_cards", "is_active")

    op.create_unique_constraint("uq_user_cards_user_id", "user_cards", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_user_cards_user_id", "user_cards", type_="unique")

    op.add_column(
        "user_cards",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "user_cards",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )
