import logging
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import VALID_TRANSITIONS, TransactionStatus, TransactionType
from app.exceptions import (
    DuplicateIdempotencyKeyError,
    InvalidTransactionStateError,
)
from app.model.transaction import Transaction
from app.repository.card_repository import CardRepository
from app.repository.transaction_repository import (
    TransactionAuditRepository,
    TransactionRepository,
)
from app.service.ledger_service import LedgerService
from app.utils.libs.paystack.interfaces import PaystackMetadata, PaystackOptions
from app.utils.libs.paystack.service import PaystackService
from app.utils.libs.vtpass.interfaces import FlattenedVtpassResponse
from fastapi import HTTPException, status as http_status

_log = logging.getLogger(__name__)

_CURRENCY = "NGN"


def _get_paystack(settings) -> PaystackService:
    from app.config import app_settings  # local import avoids circular deps

    return PaystackService(
        PaystackOptions(
            base_url=app_settings.PAYSTACK_BASE_URL,
            secret_key=app_settings.PAYSTACK_SECRET_KEY,
            public_key=app_settings.PAYSTACK_PUBLIC_KEY,
            merchant_email=app_settings.PAYSTACK_MERCHANT_EMAIL,
        )
    )


class TransactionService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tx_repo = TransactionRepository(session)
        self.audit_repo = TransactionAuditRepository(session)
        self.card_repo = CardRepository(session)
        self.ledger = LedgerService(session)

    # ── public ──────────────────────────────────────────────────────────────

    async def execute_purchase(
        self,
        *,
        user_id: uuid.UUID,
        amount: Decimal,
        transaction_type: TransactionType,
        service_id: str,
        provider: str,
        idempotency_key: str,
        extra_data: dict,
        provider_callable: Callable[
            [], Awaitable[tuple[FlattenedVtpassResponse | None, str | None]]
        ],
        paystack: PaystackService,
    ) -> Transaction:
        # 1. Return existing transaction for duplicate idempotency key (fast path)
        existing = await self.tx_repo.get_by_idempotency_key(user_id, idempotency_key)

        if existing:
            return existing

        # 2. Load card
        card = await self.card_repo.get_user_card(user_id)
        if card is None or card.user_id != user_id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Payment card not found or inactive.",
            )

        # 3. Compute expected Paystack fee so it's stored even before charging
        paystack_fee = Decimal(str(paystack.transaction_charge(float(amount))))

        # 4. Create transaction record (INITIATED) — durable before any external call
        transaction = await self._record_transaction(
            user_id=user_id,
            card_id=card.id,
            amount=amount,
            paystack_fee=paystack_fee,
            transaction_type=transaction_type,
            service_id=service_id,
            provider=provider,
            idempotency_key=idempotency_key,
            extra_data=extra_data,
        )

        # 5. Move to PROCESSING and commit before hitting external services
        await self._transition(transaction, TransactionStatus.PROCESSING)
        await self.session.commit()

        # 6. Charge the card via Paystack
        paystack_ref, charge_error = await self._charge_card(
            paystack=paystack,
            authorization_code=card.authorization_code,
            email=card.email,
            amount=float(amount),
            transaction_ref=transaction.reference,
        )

        if charge_error:
            await self._handle_failure(transaction, charge_error)
            await self.session.refresh(transaction)
            return transaction

        transaction.paystack_reference = paystack_ref
        self.session.add(transaction)
        await self.session.commit()

        # 7. Verify the charge actually settled on Paystack before calling VTpass
        if paystack_ref is None:
            await self._handle_failure(
                transaction, "Paystack charge returned no reference"
            )
            await self.session.refresh(transaction)
            return transaction

        verified = await self._verify_paystack_charge(paystack, paystack_ref)

        if verified is None:
            await self._handle_failure(transaction, "Paystack charge did not settle")
            await self.session.refresh(transaction)
            return transaction

        # 8. Call VTpass — outside any DB transaction
        result, vtpass_error = await provider_callable()

        # 9. Finalise based on VTpass response
        if result is not None:
            await self._handle_success(transaction, result, paystack=paystack)
        elif vtpass_error is not None:
            await self._handle_vtpass_failure(
                transaction, vtpass_error, paystack=paystack
            )
        else:
            await self._handle_unknown(transaction)

        await self.session.refresh(transaction)
        return transaction

    async def transition_status(
        self,
        transaction: Transaction,
        new_status: TransactionStatus,
        actor: str = "system",
    ) -> None:
        await self._transition(transaction, new_status, actor=actor)

    async def reconcile_transaction(
        self,
        transaction: Transaction,
        vtpass_status: str,
        provider_reference: str | None = None,
        paystack: PaystackService | None = None,
    ) -> Transaction:
        if vtpass_status == "delivered":
            await self._handle_success_status(transaction, provider_reference)
        elif vtpass_status in ("failed", "reversed"):
            await self._handle_vtpass_failure(
                transaction,
                "Confirmed failed by reconciliation",
                paystack=paystack,
            )
        else:
            _log.warning(
                "Reconciliation: unresolved status=%s txn=%s",
                vtpass_status,
                transaction.id,
            )

        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    # ── private helpers ──────────────────────────────────────────────────────

    async def _record_transaction(
        self,
        *,
        user_id: uuid.UUID,
        card_id: uuid.UUID,
        amount: Decimal,
        paystack_fee: Decimal,
        transaction_type: TransactionType,
        service_id: str,
        provider: str,
        idempotency_key: str,
        extra_data: dict,
    ) -> Transaction:
        reference = f"TXN{uuid.uuid4().hex.upper()}"
        transaction = Transaction(
            reference=reference,
            user_id=user_id,
            card_id=card_id,
            type=transaction_type,
            status=TransactionStatus.INITIATED,
            amount=amount,
            currency=_CURRENCY,
            provider=provider,
            service_id=service_id,
            paystack_fee=paystack_fee,
            idempotency_key=idempotency_key,
            extra_data=extra_data,
        )
        try:
            await self.tx_repo.add(transaction)
        except IntegrityError:
            await self.session.rollback()
            existing = await self.tx_repo.get_by_idempotency_key(
                user_id, idempotency_key
            )
            if existing:
                return existing
            raise DuplicateIdempotencyKeyError("Concurrent duplicate request detected.")

        # Ledger: record the payment-received and service-clearing entries
        user_account = await self.ledger.get_or_create_user_account(user_id, _CURRENCY)
        clearing_account = await self.ledger.get_or_create_clearing_account(_CURRENCY)
        await self.ledger.create_purchase_entries(
            transaction_id=transaction.id,
            user_account_id=user_account.id,
            clearing_account_id=clearing_account.id,
            amount=amount,
            currency=_CURRENCY,
        )

        await self.audit_repo.create_audit(
            transaction_id=transaction.id,
            event_type="TRANSACTION_CREATED",
            new_status=TransactionStatus.INITIATED.value,
        )
        await self.session.commit()
        return transaction

    async def _verify_paystack_charge(
        self,
        paystack: PaystackService,
        reference: str,
    ) -> dict | None:
        """Verify a charge_authorization result; returns data dict on success, None on failure."""
        try:
            resp = await paystack.verify_payment(reference)
            txn_status = (resp.get("data") or {}).get("status")

            if txn_status == "success":
                return resp.get("data")

            return None
        except Exception as exc:
            _log.warning("Paystack verify error for ref=%s: %s", reference, exc)
            return None

    async def _charge_card(
        self,
        *,
        paystack: PaystackService,
        authorization_code: str,
        email: str,
        amount: float,
        transaction_ref: str,
    ) -> tuple[str | None, str | None]:
        try:
            resp = await paystack.charge_customer(
                amount=amount,
                card_authorization_code=authorization_code,
                user_email=email,
                metadata=PaystackMetadata(extra_data={"internal_ref": transaction_ref}),
            )

            if resp.get("data", {}).get("status") in ("success", "successs"):
                return resp["data"]["reference"], None

            gateway_msg = resp.get("data", {}).get("gateway_response") or resp.get(
                "message", "Card charge failed"
            )

            return None, gateway_msg
        except Exception as exc:
            _log.error("Paystack charge failed for ref=%s: %s", transaction_ref, exc)
            return None, getattr(exc, "detail", str(exc)) or "Card charge failed"

    async def _handle_success(
        self,
        transaction: Transaction,
        result: FlattenedVtpassResponse,
        paystack: PaystackService,
    ) -> None:
        vtpass_cost = Decimal(str(result.total_amount or result.amount or 0))

        profit_loss = (
            transaction.amount
            - (transaction.paystack_fee or Decimal("0"))
            - vtpass_cost
        )

        transaction.vtpass_cost = vtpass_cost
        transaction.profit_loss = profit_loss
        self.session.add(transaction)

        await self._handle_success_status(transaction, result.request_id)

    async def _handle_success_status(
        self, transaction: Transaction, provider_reference: str | None
    ) -> None:
        transaction.provider_reference = provider_reference
        await self._transition(transaction, TransactionStatus.SUCCESSFUL)
        await self.session.commit()

    async def _handle_failure(self, transaction: Transaction, reason: str) -> None:
        """Paystack charge itself failed — no money moved, no refund needed."""
        await self._transition(transaction, TransactionStatus.FAILED)
        transaction.failure_reason = reason
        self.session.add(transaction)
        # No reversal entries needed — no card was charged
        await self.session.commit()

    async def _handle_vtpass_failure(
        self, transaction: Transaction, reason: str, paystack: PaystackService | None
    ) -> None:
        """Card was charged but VTpass failed — issue Paystack refund."""
        await self._transition(transaction, TransactionStatus.FAILED)
        transaction.failure_reason = reason
        self.session.add(transaction)

        # Compensating ledger entries for the refund
        user_account = await self.ledger.get_or_create_user_account(
            transaction.user_id, _CURRENCY
        )
        clearing_account = await self.ledger.get_or_create_clearing_account(_CURRENCY)
        await self.ledger.create_reversal_entries(
            transaction_id=transaction.id,
            user_account_id=user_account.id,
            clearing_account_id=clearing_account.id,
            amount=transaction.amount,
            currency=_CURRENCY,
        )

        # Issue Paystack refund if we have the reference
        if paystack and transaction.paystack_reference:
            try:
                await paystack.refund_transaction(transaction.paystack_reference)
                _log.info(
                    "Paystack refund issued for txn=%s ref=%s",
                    transaction.id,
                    transaction.paystack_reference,
                )
            except Exception as exc:
                _log.error(
                    "Paystack refund FAILED for txn=%s: %s — manual action required",
                    transaction.id,
                    exc,
                )

        await self._transition(transaction, TransactionStatus.REVERSAL_PENDING)
        await self._transition(transaction, TransactionStatus.REVERSED)
        await self.session.commit()

    async def _handle_unknown(self, transaction: Transaction) -> None:
        await self._transition(transaction, TransactionStatus.UNKNOWN)
        await self.session.commit()

    async def _transition(
        self,
        transaction: Transaction,
        new_status: TransactionStatus,
        actor: str = "system",
    ) -> None:
        current = TransactionStatus(transaction.status)
        allowed = VALID_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise InvalidTransactionStateError(
                f"Cannot transition from {current.value} to {new_status.value}"
            )
        previous = transaction.status
        transaction.status = new_status
        self.session.add(transaction)

        await self.audit_repo.create_audit(
            transaction_id=transaction.id,
            event_type="STATUS_CHANGED",
            previous_status=(
                previous.value if isinstance(previous, TransactionStatus) else previous
            ),
            new_status=new_status.value,
            actor=actor,
        )
