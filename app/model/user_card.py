import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base, TimestampMixin


class UserCard(Base, TimestampMixin):
    """Stores a Paystack reusable card authorization. One card per user (one-to-one)."""

    __tablename__ = "user_cards"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_cards_user_id"),
        Index("ix_user_cards_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    authorization_code: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    bank: Mapped[str] = mapped_column(String(100), nullable=False)
    # Paystack customer code enables lookup without re-auth
    paystack_customer_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
