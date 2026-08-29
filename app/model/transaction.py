import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.enums.transaction import TransactionStatus, TransactionType
from app.model.base import Base, TimestampMixin


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_transactions_user_idempotency"),
        Index("ix_transactions_provider_reference", "provider_reference"),
        Index("ix_transactions_reference", "reference"),
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_paystack_reference", "paystack_reference"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Card used to pay; nullable so UNKNOWN transactions keep their record if card is later removed
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_cards.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[TransactionType] = mapped_column(String(20), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        String(20), nullable=False, default=TransactionStatus.INITIATED
    )
    # Selling price — what the user was charged
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    service_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # VTpass request_id returned after provider call
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Paystack charge reference for reconciliation / refund
    paystack_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Paystack fee deducted from our settlement
    paystack_fee: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)
    # Actual cost VTpass charged us (FlattenedVtpassResponse.total_amount after success)
    vtpass_cost: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)
    # Profit/loss = amount - paystack_fee - vtpass_cost (positive = profit)
    profit_loss: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
