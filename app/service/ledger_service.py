import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import LedgerAccountType, LedgerEntryDirection
from app.exceptions import AppException
from app.model.ledger import LedgerAccount, LedgerEntry
from app.repository.ledger_repository import (
    LedgerAccountRepository,
    LedgerEntryRepository,
)


class LedgerService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.account_repo = LedgerAccountRepository(session)
        self.entry_repo = LedgerEntryRepository(session)

    async def get_or_create_user_account(
        self, user_id: uuid.UUID, currency: str
    ) -> LedgerAccount:
        reference = f"USER_WALLET:{user_id}:{currency}"
        return await self.account_repo.get_or_create(
            reference=reference,
            account_type=LedgerAccountType.USER_WALLET,
            currency=currency,
            description=f"Wallet ledger account for user {user_id}",
        )

    async def get_or_create_clearing_account(self, currency: str) -> LedgerAccount:
        reference = f"PROVIDER_CLEARING:{currency}"
        return await self.account_repo.get_or_create(
            reference=reference,
            account_type=LedgerAccountType.PROVIDER_CLEARING,
            currency=currency,
            description=f"Provider clearing account for {currency}",
        )

    async def create_purchase_entries(
        self,
        transaction_id: uuid.UUID,
        user_account_id: uuid.UUID,
        clearing_account_id: uuid.UUID,
        amount: Decimal,
        currency: str,
    ) -> list[LedgerEntry]:
        """Debit user wallet, credit provider clearing. Total debit == total credit."""
        debit = await self.entry_repo.create_entry(
            transaction_id=transaction_id,
            account_id=user_account_id,
            direction=LedgerEntryDirection.DEBIT,
            amount=amount,
            currency=currency,
        )
        credit = await self.entry_repo.create_entry(
            transaction_id=transaction_id,
            account_id=clearing_account_id,
            direction=LedgerEntryDirection.CREDIT,
            amount=amount,
            currency=currency,
        )
        self._assert_balanced([debit, credit])
        return [debit, credit]

    async def create_reversal_entries(
        self,
        transaction_id: uuid.UUID,
        user_account_id: uuid.UUID,
        clearing_account_id: uuid.UUID,
        amount: Decimal,
        currency: str,
    ) -> list[LedgerEntry]:
        """Compensating entries: debit clearing, credit user wallet."""
        debit = await self.entry_repo.create_entry(
            transaction_id=transaction_id,
            account_id=clearing_account_id,
            direction=LedgerEntryDirection.DEBIT,
            amount=amount,
            currency=currency,
        )
        credit = await self.entry_repo.create_entry(
            transaction_id=transaction_id,
            account_id=user_account_id,
            direction=LedgerEntryDirection.CREDIT,
            amount=amount,
            currency=currency,
        )
        self._assert_balanced([debit, credit])
        return [debit, credit]

    @staticmethod
    def _assert_balanced(entries: list[LedgerEntry]) -> None:
        total_debit = sum(
            e.amount for e in entries if e.direction == LedgerEntryDirection.DEBIT
        )
        total_credit = sum(
            e.amount for e in entries if e.direction == LedgerEntryDirection.CREDIT
        )
        if total_debit != total_credit:
            raise AppException(
                f"Ledger imbalance: debit={total_debit}, credit={total_credit}"
            )
