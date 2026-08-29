import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import LedgerAccountType, LedgerEntryDirection
from app.model.ledger import LedgerAccount, LedgerEntry
from app.repository.base import BaseRepository


class LedgerAccountRepository(BaseRepository[LedgerAccount]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LedgerAccount, session)

    async def get_by_reference(self, reference: str) -> LedgerAccount | None:
        result = await self.session.execute(
            select(LedgerAccount).where(LedgerAccount.reference == reference)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        reference: str,
        account_type: LedgerAccountType,
        currency: str,
        description: str | None = None,
    ) -> LedgerAccount:
        account = await self.get_by_reference(reference)
        if account:
            return account
        account = LedgerAccount(
            account_type=account_type,
            reference=reference,
            currency=currency,
            description=description,
        )
        return await self.add(account)


class LedgerEntryRepository(BaseRepository[LedgerEntry]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LedgerEntry, session)

    async def get_by_transaction(self, transaction_id: uuid.UUID) -> list[LedgerEntry]:
        result = await self.session.execute(
            select(LedgerEntry).where(LedgerEntry.transaction_id == transaction_id)
        )
        return list(result.scalars().all())

    async def create_entry(
        self,
        transaction_id: uuid.UUID,
        account_id: uuid.UUID,
        direction: LedgerEntryDirection,
        amount: Decimal,
        currency: str,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            transaction_id=transaction_id,
            account_id=account_id,
            direction=direction,
            amount=amount,
            currency=currency,
        )
        return await self.add(entry)
