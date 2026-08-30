import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionType
from app.model.transaction import Transaction
from app.service.transaction_service import TransactionService
from app.utils.libs.vtpass.interfaces import BuyAirtimeData
from app.utils.libs.vtpass.service import VtpassService
from app.schema.common import AIRTIME_PROVIDERS


class AirtimeService:

    def __init__(self, session: AsyncSession, vtpass: VtpassService) -> None:
        self.session = session
        self.vtpass = vtpass
        self.tx_service = TransactionService(session)

    def providers(self) -> list[str]:
        return sorted(AIRTIME_PROVIDERS)

    async def purchase(
        self,
        user_id: uuid.UUID,
        service_id: str,
        phone: str,
        amount: Decimal,
        idempotency_key: str,
        paystack,
    ) -> Transaction:
        if service_id not in AIRTIME_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider. Supported: {sorted(AIRTIME_PROVIDERS)}",
            )

        vtpass = self.vtpass

        async def _call():
            return await vtpass.buy_airtime(
                BuyAirtimeData(service_id=service_id, phone=phone, amount=str(amount))
            )

        return await self.tx_service.execute_purchase(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.AIRTIME,
            service_id=service_id,
            provider=service_id,
            idempotency_key=idempotency_key,
            extra_data={"phone": phone},
            provider_callable=_call,
            paystack=paystack,
        )
