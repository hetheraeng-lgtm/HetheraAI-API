import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.enums.transaction import TransactionStatus, TransactionType


class TransactionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    chat_id: str
    type: TransactionType
    status: TransactionStatus
    amount: Decimal
    currency: str
    provider: str
    service_id: str
    provider_reference: str | None
    paystack_reference: str | None
    created_at: datetime


class TransactionListResponse(BaseModel):
    records: list[TransactionListItem]
    totalPages: int
    totalRecords: int


class TransactionAuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    previous_status: str | None
    new_status: str | None
    audit_metadata: dict | None
    actor: str | None
    created_at: datetime


class LedgerEntryItem(BaseModel):
    id: uuid.UUID
    account_type: str
    account_reference: str
    direction: str
    amount: Decimal
    currency: str
    created_at: datetime


class TransactionDetailResponse(BaseModel):
    id: uuid.UUID
    reference: str
    chat_id: str
    type: TransactionType
    status: TransactionStatus
    amount: Decimal
    currency: str
    provider: str
    service_id: str
    provider_reference: str | None
    paystack_reference: str | None
    paystack_fee: Decimal | None
    vtpass_cost: Decimal | None
    profit_loss: Decimal | None
    idempotency_key: str
    extra_data: dict | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    audit_trail: list[TransactionAuditItem]
    ledger_entries: list[LedgerEntryItem]
