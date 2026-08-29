"""Shared test fixtures."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionStatus, TransactionType
from app.model.ledger import LedgerAccount, LedgerEntry
from app.model.transaction import Transaction
from app.model.transaction_audit import TransactionAudit
from app.model.wallet import Wallet
from app.utils.libs.vtpass.interfaces import FlattenedVtpassResponse


def _make_wallet(user_id: uuid.UUID, balance: Decimal = Decimal("5000.00")) -> Wallet:
    w = Wallet()
    w.id = uuid.uuid4()
    w.user_id = user_id
    w.balance = balance
    w.currency = "NGN"
    return w


def _make_transaction(
    user_id: uuid.UUID,
    wallet_id: uuid.UUID,
    amount: Decimal = Decimal("100.00"),
    status: TransactionStatus = TransactionStatus.INITIATED,
    tx_type: TransactionType = TransactionType.AIRTIME,
) -> Transaction:
    t = Transaction()
    t.id = uuid.uuid4()
    t.reference = f"TXN{uuid.uuid4().hex.upper()}"
    t.user_id = user_id
    t.wallet_id = wallet_id
    t.type = tx_type
    t.status = status
    t.amount = amount
    t.currency = "NGN"
    t.provider = "mtn"
    t.service_id = "mtn"
    t.idempotency_key = str(uuid.uuid4())
    t.extra_data = {}
    return t


def _vtpass_success(request_id: str = "test-req-id") -> FlattenedVtpassResponse:
    return FlattenedVtpassResponse(
        request_id=request_id,
        status="delivered",
        amount=100.0,
        total_amount=100.0,
        product_name="MTN Airtime",
        unique_element="08012345678",
        request_description="Transaction successful",
        vt_pass_transaction_id="VTP-123",
    )
