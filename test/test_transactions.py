"""
Unit tests for the transaction/ledger/utility-service layer.

All database and VTpass calls are mocked — no real DB or network needed.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.transaction import (
    LedgerEntryDirection,
    TransactionStatus,
    TransactionType,
)
from app.exceptions import (
    InsufficientBalanceError,
    InvalidTransactionStateError,
    WalletNotFoundError,
)
from app.model.ledger import LedgerAccount, LedgerEntry
from app.model.transaction import Transaction
from app.model.wallet import Wallet
from app.service.ledger_service import LedgerService
from app.service.transaction_service import TransactionService
from app.utils.libs.vtpass.interfaces import FlattenedVtpassResponse
from test.conftest import _make_transaction, _make_wallet, _vtpass_success

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


def _ledger_account(ref: str) -> LedgerAccount:
    a = LedgerAccount()
    a.id = uuid.uuid4()
    a.reference = ref
    a.currency = "NGN"
    return a


def _ledger_entry(
    direction: LedgerEntryDirection, amount: Decimal = Decimal("100.00")
) -> LedgerEntry:
    e = LedgerEntry()
    e.id = uuid.uuid4()
    e.direction = direction
    e.amount = amount
    e.currency = "NGN"
    return e


# ── LedgerService ─────────────────────────────────────────────────────────────


class TestLedgerService:

    def _svc(self, session=None):
        session = session or _make_session()
        svc = LedgerService(session)
        return svc

    @pytest.mark.asyncio
    async def test_create_purchase_entries_balanced(self):
        svc = self._svc()
        user_acc = _ledger_account("user")
        clearing_acc = _ledger_account("clearing")
        amount = Decimal("200.00")

        debit = _ledger_entry(LedgerEntryDirection.DEBIT, amount)
        credit = _ledger_entry(LedgerEntryDirection.CREDIT, amount)

        svc.entry_repo.create_entry = AsyncMock(side_effect=[debit, credit])

        entries = await svc.create_purchase_entries(
            transaction_id=uuid.uuid4(),
            user_account_id=user_acc.id,
            clearing_account_id=clearing_acc.id,
            amount=amount,
            currency="NGN",
        )

        assert len(entries) == 2
        debits = [e for e in entries if e.direction == LedgerEntryDirection.DEBIT]
        credits = [e for e in entries if e.direction == LedgerEntryDirection.CREDIT]
        assert sum(e.amount for e in debits) == sum(e.amount for e in credits)

    @pytest.mark.asyncio
    async def test_create_reversal_entries_balanced(self):
        svc = self._svc()
        amount = Decimal("150.00")
        debit = _ledger_entry(LedgerEntryDirection.DEBIT, amount)
        credit = _ledger_entry(LedgerEntryDirection.CREDIT, amount)
        svc.entry_repo.create_entry = AsyncMock(side_effect=[debit, credit])

        entries = await svc.create_reversal_entries(
            transaction_id=uuid.uuid4(),
            user_account_id=uuid.uuid4(),
            clearing_account_id=uuid.uuid4(),
            amount=amount,
            currency="NGN",
        )
        debits = [e for e in entries if e.direction == LedgerEntryDirection.DEBIT]
        credits = [e for e in entries if e.direction == LedgerEntryDirection.CREDIT]
        assert sum(e.amount for e in debits) == sum(e.amount for e in credits)

    def test_assert_balanced_raises_on_imbalance(self):
        from app.exceptions import AppException

        e1 = _ledger_entry(LedgerEntryDirection.DEBIT, Decimal("100.00"))
        e2 = _ledger_entry(LedgerEntryDirection.CREDIT, Decimal("99.00"))
        with pytest.raises(AppException):
            LedgerService._assert_balanced([e1, e2])


# ── TransactionService state transitions ─────────────────────────────────────


class TestTransactionStateTransitions:

    def _svc(self):
        session = _make_session()
        svc = TransactionService(session)
        svc.audit_repo.create_audit = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_valid_initiated_to_processing(self):
        svc = self._svc()
        txn = _make_transaction(
            uuid.uuid4(), uuid.uuid4(), status=TransactionStatus.INITIATED
        )
        await svc._transition(txn, TransactionStatus.PROCESSING)
        assert txn.status == TransactionStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self):
        svc = self._svc()
        txn = _make_transaction(
            uuid.uuid4(), uuid.uuid4(), status=TransactionStatus.SUCCESSFUL
        )
        with pytest.raises(InvalidTransactionStateError):
            await svc._transition(txn, TransactionStatus.PROCESSING)

    @pytest.mark.asyncio
    async def test_reversed_to_successful_is_invalid(self):
        svc = self._svc()
        txn = _make_transaction(
            uuid.uuid4(), uuid.uuid4(), status=TransactionStatus.REVERSED
        )
        with pytest.raises(InvalidTransactionStateError):
            await svc._transition(txn, TransactionStatus.SUCCESSFUL)

    @pytest.mark.asyncio
    async def test_processing_to_failed_is_valid(self):
        svc = self._svc()
        txn = _make_transaction(
            uuid.uuid4(), uuid.uuid4(), status=TransactionStatus.PROCESSING
        )
        await svc._transition(txn, TransactionStatus.FAILED)
        assert txn.status == TransactionStatus.FAILED

    @pytest.mark.asyncio
    async def test_unknown_to_successful_is_valid(self):
        svc = self._svc()
        txn = _make_transaction(
            uuid.uuid4(), uuid.uuid4(), status=TransactionStatus.UNKNOWN
        )
        await svc._transition(txn, TransactionStatus.SUCCESSFUL)
        assert txn.status == TransactionStatus.SUCCESSFUL


# ── TransactionService execute_purchase ──────────────────────────────────────


class TestTransactionServiceExecutePurchase:

    def _build_svc(self, wallet: Wallet):
        session = _make_session()
        svc = TransactionService(session)
        svc.tx_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        svc.wallet_repo.get_by_user_id_with_lock = AsyncMock(return_value=wallet)
        svc.audit_repo.create_audit = AsyncMock()
        # ledger helpers
        user_acc = _ledger_account("user")
        clearing_acc = _ledger_account("clearing")
        svc.ledger.get_or_create_user_account = AsyncMock(return_value=user_acc)
        svc.ledger.get_or_create_clearing_account = AsyncMock(return_value=clearing_acc)
        debit = _ledger_entry(LedgerEntryDirection.DEBIT)
        credit = _ledger_entry(LedgerEntryDirection.CREDIT)
        svc.ledger.create_purchase_entries = AsyncMock(return_value=[debit, credit])
        svc.ledger.create_reversal_entries = AsyncMock(
            return_value=[
                _ledger_entry(LedgerEntryDirection.DEBIT),
                _ledger_entry(LedgerEntryDirection.CREDIT),
            ]
        )
        return svc

    def _make_txn(self, user_id, wallet_id):
        txn = _make_transaction(user_id, wallet_id, status=TransactionStatus.INITIATED)
        return txn

    @pytest.mark.asyncio
    async def test_successful_purchase_marks_successful(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("1000.00"))
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        svc.tx_repo.add = AsyncMock(return_value=txn)
        session_refresh_call = 0

        async def _refresh(obj):
            nonlocal session_refresh_call
            session_refresh_call += 1

        svc.session.refresh = _refresh

        success_response = _vtpass_success()

        result = await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(success_response, None)),
        )

        assert result.status == TransactionStatus.SUCCESSFUL

    @pytest.mark.asyncio
    async def test_insufficient_balance_raises(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("50.00"))
        svc = self._build_svc(wallet)

        with pytest.raises(InsufficientBalanceError):
            await svc.execute_purchase(
                user_id=user_id,
                amount=Decimal("100.00"),
                transaction_type=TransactionType.AIRTIME,
                service_id="mtn",
                provider="mtn",
                idempotency_key=str(uuid.uuid4()),
                extra_data={},
                provider_callable=AsyncMock(return_value=(_vtpass_success(), None)),
            )

    @pytest.mark.asyncio
    async def test_no_provider_call_when_balance_insufficient(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("0.00"))
        svc = self._build_svc(wallet)
        callable_mock = AsyncMock(return_value=(_vtpass_success(), None))

        with pytest.raises(InsufficientBalanceError):
            await svc.execute_purchase(
                user_id=user_id,
                amount=Decimal("100.00"),
                transaction_type=TransactionType.AIRTIME,
                service_id="mtn",
                provider="mtn",
                idempotency_key=str(uuid.uuid4()),
                extra_data={},
                provider_callable=callable_mock,
            )

        callable_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_wallet_not_found_raises(self):
        user_id = uuid.uuid4()
        session = _make_session()
        svc = TransactionService(session)
        svc.tx_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        svc.wallet_repo.get_by_user_id_with_lock = AsyncMock(return_value=None)

        with pytest.raises(WalletNotFoundError):
            await svc.execute_purchase(
                user_id=user_id,
                amount=Decimal("100.00"),
                transaction_type=TransactionType.AIRTIME,
                service_id="mtn",
                provider="mtn",
                idempotency_key=str(uuid.uuid4()),
                extra_data={},
                provider_callable=AsyncMock(),
            )

    @pytest.mark.asyncio
    async def test_duplicate_idempotency_key_returns_existing(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id)
        existing_txn = _make_transaction(
            user_id, wallet.id, status=TransactionStatus.SUCCESSFUL
        )

        session = _make_session()
        svc = TransactionService(session)
        svc.tx_repo.get_by_idempotency_key = AsyncMock(return_value=existing_txn)
        callable_mock = AsyncMock(return_value=(_vtpass_success(), None))

        result = await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key="same-key",
            extra_data={},
            provider_callable=callable_mock,
        )

        assert result is existing_txn
        callable_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_failure_triggers_reversal(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("1000.00"))
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        svc.tx_repo.add = AsyncMock(return_value=txn)
        svc.session.refresh = AsyncMock()

        result = await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(None, "Provider rejected")),
        )

        assert result.status == TransactionStatus.REVERSED
        assert result.failure_reason == "Provider rejected"

    @pytest.mark.asyncio
    async def test_provider_timeout_marks_unknown(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("1000.00"))
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        svc.tx_repo.add = AsyncMock(return_value=txn)
        svc.session.refresh = AsyncMock()

        # Both result and error are None == unknown outcome
        result = await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(None, None)),
        )

        assert result.status == TransactionStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_reversal_restores_wallet_balance(self):
        user_id = uuid.uuid4()
        initial_balance = Decimal("1000.00")
        purchase_amount = Decimal("200.00")
        wallet = _make_wallet(user_id, initial_balance)
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        txn.amount = purchase_amount
        svc.tx_repo.add = AsyncMock(return_value=txn)
        svc.session.refresh = AsyncMock()
        # Re-lock returns same wallet for reversal path
        svc.wallet_repo.get_by_user_id_with_lock = AsyncMock(return_value=wallet)

        await svc.execute_purchase(
            user_id=user_id,
            amount=purchase_amount,
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(None, "failed")),
        )

        # balance was debited, then restored: net = initial
        assert wallet.balance == initial_balance - purchase_amount + purchase_amount

    @pytest.mark.asyncio
    async def test_reversal_creates_compensating_ledger_entries(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("500.00"))
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        svc.tx_repo.add = AsyncMock(return_value=txn)
        svc.session.refresh = AsyncMock()

        await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(None, "failed")),
        )

        svc.ledger.create_reversal_entries.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_transaction_not_auto_reversed(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id, Decimal("500.00"))
        svc = self._build_svc(wallet)
        txn = self._make_txn(user_id, wallet.id)
        svc.tx_repo.add = AsyncMock(return_value=txn)
        svc.session.refresh = AsyncMock()

        result = await svc.execute_purchase(
            user_id=user_id,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.AIRTIME,
            service_id="mtn",
            provider="mtn",
            idempotency_key=str(uuid.uuid4()),
            extra_data={},
            provider_callable=AsyncMock(return_value=(None, None)),
        )

        assert result.status == TransactionStatus.UNKNOWN
        svc.ledger.create_reversal_entries.assert_not_called()


# ── Reconciliation ────────────────────────────────────────────────────────────


class TestReconciliation:

    def _svc(self, txn: Transaction, wallet: Wallet):
        session = _make_session()
        svc = TransactionService(session)
        svc.audit_repo.create_audit = AsyncMock()
        svc.wallet_repo.get_by_user_id_with_lock = AsyncMock(return_value=wallet)
        user_acc = _ledger_account("user")
        clearing_acc = _ledger_account("clearing")
        svc.ledger.get_or_create_user_account = AsyncMock(return_value=user_acc)
        svc.ledger.get_or_create_clearing_account = AsyncMock(return_value=clearing_acc)
        svc.ledger.create_reversal_entries = AsyncMock(
            return_value=[
                _ledger_entry(LedgerEntryDirection.DEBIT),
                _ledger_entry(LedgerEntryDirection.CREDIT),
            ]
        )
        return svc

    @pytest.mark.asyncio
    async def test_reconcile_delivered_marks_successful(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id)
        txn = _make_transaction(user_id, wallet.id, status=TransactionStatus.UNKNOWN)
        svc = self._svc(txn, wallet)
        svc.session.refresh = AsyncMock()

        result = await svc.reconcile_transaction(txn, "delivered", "prov-ref-123")

        assert result.status == TransactionStatus.SUCCESSFUL

    @pytest.mark.asyncio
    async def test_reconcile_failed_triggers_reversal(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id)
        txn = _make_transaction(user_id, wallet.id, status=TransactionStatus.UNKNOWN)
        svc = self._svc(txn, wallet)
        svc.session.refresh = AsyncMock()

        result = await svc.reconcile_transaction(txn, "failed")

        assert result.status == TransactionStatus.REVERSED

    @pytest.mark.asyncio
    async def test_reconcile_success_does_not_reverse(self):
        user_id = uuid.uuid4()
        wallet = _make_wallet(user_id)
        txn = _make_transaction(user_id, wallet.id, status=TransactionStatus.UNKNOWN)
        svc = self._svc(txn, wallet)
        svc.session.refresh = AsyncMock()

        await svc.reconcile_transaction(txn, "delivered")

        svc.ledger.create_reversal_entries.assert_not_called()
