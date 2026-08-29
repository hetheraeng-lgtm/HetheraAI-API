import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.enums.transaction import LedgerAccountType, LedgerEntryDirection
from app.model.base import Base, TimestampMixin
from zoneinfo import ZoneInfo

_WAT = ZoneInfo("Africa/Lagos")


class LedgerAccount(Base, TimestampMixin):
    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_type: Mapped[LedgerAccountType] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LedgerEntry(Base):
    """Immutable — no updated_at."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    direction: Mapped[LedgerEntryDirection] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        default=lambda: datetime.now(_WAT),
    )
