import math
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionStatus, TransactionType
from app.model.ledger import LedgerAccount, LedgerEntry
from app.model.transaction import Transaction
from app.model.user import User
from app.repository.ledger_repository import LedgerEntryRepository
from app.repository.transaction_repository import TransactionAuditRepository
from app.schema.admin_transaction import (
    LedgerEntryItem,
    TransactionAuditItem,
    TransactionDetailResponse,
    TransactionListItem,
    TransactionListResponse,
)


class AdminTransactionService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_transactions(
        self,
        *,
        page: int = 0,
        size: int = 20,
        search: str | None = None,
        status_: TransactionStatus | None = None,
        type_: TransactionType | None = None,
        provider: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        user_id: uuid.UUID | None = None,
    ) -> TransactionListResponse:
        conditions = []

        if search:
            like = f"%{search}%"
            conditions.append(
                (Transaction.reference.ilike(like))
                | (Transaction.provider_reference.ilike(like))
                | (Transaction.paystack_reference.ilike(like))
                | (User.chat_id.ilike(like))
            )
        if status_:
            conditions.append(Transaction.status == status_)
        if type_:
            conditions.append(Transaction.type == type_)
        if provider:
            conditions.append(Transaction.provider == provider)
        if date_from:
            conditions.append(Transaction.created_at >= date_from)
        if date_to:
            conditions.append(Transaction.created_at <= date_to)
        if min_amount is not None:
            conditions.append(Transaction.amount >= min_amount)
        if max_amount is not None:
            conditions.append(Transaction.amount <= max_amount)
        if user_id:
            conditions.append(Transaction.user_id == user_id)

        base_query = select(Transaction, User.chat_id).join(User, Transaction.user_id == User.id)
        for condition in conditions:
            base_query = base_query.where(condition)

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_records = (await self.session.execute(count_stmt)).scalar_one()

        page_stmt = (
            base_query.order_by(Transaction.created_at.desc()).offset(page * size).limit(size)
        )
        rows = (await self.session.execute(page_stmt)).all()

        records = [
            TransactionListItem(
                id=txn.id,
                reference=txn.reference,
                chat_id=chat_id,
                type=txn.type,
                status=txn.status,
                amount=txn.amount,
                currency=txn.currency,
                provider=txn.provider,
                service_id=txn.service_id,
                provider_reference=txn.provider_reference,
                paystack_reference=txn.paystack_reference,
                created_at=txn.created_at,
            )
            for txn, chat_id in rows
        ]

        total_pages = math.ceil(total_records / size) if size else 0

        return TransactionListResponse(
            records=records, totalPages=total_pages, totalRecords=total_records
        )

    async def get_detail(self, reference: str) -> TransactionDetailResponse:
        stmt = select(Transaction, User.chat_id).join(User, Transaction.user_id == User.id).where(
            Transaction.reference == reference
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
            )
        txn, chat_id = row

        audit_repo = TransactionAuditRepository(self.session)
        audits = await audit_repo.get_for_transaction(txn.id)

        ledger_repo = LedgerEntryRepository(self.session)
        entries = await ledger_repo.get_by_transaction(txn.id)
        account_ids = {e.account_id for e in entries}
        accounts: dict[uuid.UUID, LedgerAccount] = {}
        if account_ids:
            acc_rows = (
                await self.session.execute(
                    select(LedgerAccount).where(LedgerAccount.id.in_(account_ids))
                )
            ).scalars().all()
            accounts = {a.id: a for a in acc_rows}

        return TransactionDetailResponse(
            id=txn.id,
            reference=txn.reference,
            chat_id=chat_id,
            type=txn.type,
            status=txn.status,
            amount=txn.amount,
            currency=txn.currency,
            provider=txn.provider,
            service_id=txn.service_id,
            provider_reference=txn.provider_reference,
            paystack_reference=txn.paystack_reference,
            paystack_fee=txn.paystack_fee,
            vtpass_cost=txn.vtpass_cost,
            profit_loss=txn.profit_loss,
            idempotency_key=txn.idempotency_key,
            extra_data=txn.extra_data,
            failure_reason=txn.failure_reason,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
            audit_trail=[TransactionAuditItem.model_validate(a) for a in audits],
            ledger_entries=[
                LedgerEntryItem(
                    id=e.id,
                    account_type=str(accounts[e.account_id].account_type)
                    if e.account_id in accounts
                    else "unknown",
                    account_reference=accounts[e.account_id].reference
                    if e.account_id in accounts
                    else "unknown",
                    direction=str(e.direction),
                    amount=e.amount,
                    currency=e.currency,
                    created_at=e.created_at,
                )
                for e in entries
            ],
        )
