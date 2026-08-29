"""Add user_cards, beneficiaries; migrate transactions to card-based payments

Revision ID: d7e2f3a4b5c6
Revises: c3f9a1b2d4e5
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c3f9a1b2d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user_cards ────────────────────────────────────────────────────────────
    op.create_table(
        "user_cards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("authorization_code", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=False),
        sa.Column("card_type", sa.String(length=50), nullable=False),
        sa.Column("bank", sa.String(length=100), nullable=False),
        sa.Column("paystack_customer_code", sa.String(length=100), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_cards_user_id", "user_cards", ["user_id"])

    # ── beneficiaries ─────────────────────────────────────────────────────────
    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("service_id", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_beneficiaries_user_id", "beneficiaries", ["user_id"])

    # ── alter transactions ────────────────────────────────────────────────────

    # Drop wallet FK / column if it exists (it may not if tables were never migrated)
    with op.batch_alter_table("transactions") as batch_op:
        try:
            batch_op.drop_constraint("transactions_wallet_id_fkey", type_="foreignkey")
        except Exception:
            pass
        try:
            batch_op.drop_column("wallet_id")
        except Exception:
            pass

    # Add new columns
    op.add_column(
        "transactions",
        sa.Column("card_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_card_id",
        "transactions",
        "user_cards",
        ["card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "transactions",
        sa.Column("paystack_reference", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("paystack_fee", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("vtpass_cost", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("profit_loss", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.create_index(
        "ix_transactions_paystack_reference", "transactions", ["paystack_reference"]
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_paystack_reference", table_name="transactions")
    op.drop_constraint("fk_transactions_card_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "profit_loss")
    op.drop_column("transactions", "vtpass_cost")
    op.drop_column("transactions", "paystack_fee")
    op.drop_column("transactions", "paystack_reference")
    op.drop_column("transactions", "card_id")

    op.drop_index("ix_beneficiaries_user_id", table_name="beneficiaries")
    op.drop_table("beneficiaries")

    op.drop_index("ix_user_cards_user_id", table_name="user_cards")
    op.drop_table("user_cards")
