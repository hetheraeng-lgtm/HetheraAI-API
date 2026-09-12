import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionStatus
from app.model.transaction import Transaction
from app.model.transaction_audit import TransactionAudit
from app.repository.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transaction, session)

    async def get_by_reference(self, reference: str) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(Transaction.reference == reference)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self, user_id: uuid.UUID, idempotency_key: str
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider_reference(
        self, provider_reference: str
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.provider_reference == provider_reference
            )
        )
        return result.scalar_one_or_none()

    async def get_by_paystack_reference(
        self, paystack_reference: str
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.paystack_reference == paystack_reference
            )
        )
        return result.scalar_one_or_none()

    async def get_unresolved(self) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.status.in_(
                    [TransactionStatus.UNKNOWN, TransactionStatus.PROCESSING]
                )
            )
        )
        return list(result.scalars().all())

    async def get_user_transactions(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 20
    ) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


class TransactionAuditRepository(BaseRepository[TransactionAudit]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TransactionAudit, session)

    async def create_audit(
        self,
        transaction_id: uuid.UUID,
        event_type: str,
        previous_status: str | None = None,
        new_status: str | None = None,
        metadata: dict | None = None,
        actor: str = "system",
    ) -> TransactionAudit:
        audit = TransactionAudit(
            transaction_id=transaction_id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            audit_metadata=metadata,
            actor=actor,
        )
        return await self.add(audit)

    async def get_for_transaction(self, transaction_id: uuid.UUID) -> list[TransactionAudit]:
        result = await self.session.execute(
            select(TransactionAudit)
            .where(TransactionAudit.transaction_id == transaction_id)
            .order_by(TransactionAudit.created_at.asc())
        )
        return list(result.scalars().all())
