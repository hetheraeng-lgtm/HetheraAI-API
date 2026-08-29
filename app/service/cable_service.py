import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionType
from app.exceptions import ProviderValidationError
from app.model.transaction import Transaction
from app.schema.common import CABLE_PROVIDERS
from app.service.transaction_service import TransactionService
from app.utils.libs.vtpass.interfaces import (
    BuyCableData,
    VerifyMeterNumberData,
    VtpassVerifyResponse,
)
from app.utils.libs.vtpass.service import VtpassService


class CableService:

    def __init__(self, session: AsyncSession, vtpass: VtpassService) -> None:
        self.session = session
        self.vtpass = vtpass
        self.tx_service = TransactionService(session)

    def providers(self) -> list[str]:
        return sorted(CABLE_PROVIDERS)

    async def get_variation_codes(self, service_id: str) -> dict:
        if service_id not in CABLE_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported cable provider. Supported: {sorted(CABLE_PROVIDERS)}",
            )
        return await self.vtpass.get_variation_codes(service_id)

    async def verify_smartcard(
        self, service_id: str, smartcard_number: str
    ) -> VtpassVerifyResponse | None:
        from app.utils.libs.vtpass.interfaces import (
            VtpassVerifyResponse as _VR,
        )  # noqa: F401

        if service_id not in CABLE_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported cable provider. Supported: {sorted(CABLE_PROVIDERS)}",
            )
        result, error = await self.vtpass.verify_merchant(
            VerifyMeterNumberData(service_id=service_id, billers_code=smartcard_number)
        )
        if error:
            raise ProviderValidationError(error)
        return result

    async def purchase(
        self,
        user_id: uuid.UUID,
        chat_id: str,
        service_id: str,
        smartcard_number: str,
        variation_code: str,
        idempotency_key: str,
        paystack,
    ) -> Transaction:
        if service_id not in CABLE_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported cable provider. Supported: {sorted(CABLE_PROVIDERS)}",
            )
        amount = await self._resolve_variation_amount(service_id, variation_code)
        vtpass = self.vtpass

        async def _call():
            return await vtpass.buy_cable(
                BuyCableData(
                    amount=str(amount),
                    subscription_type="change",
                    phone=chat_id,
                    service_id=service_id,
                    billers_code=smartcard_number,
                    variation_code=variation_code,
                )
            )

        return await self.tx_service.execute_purchase(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.CABLE_TV,
            service_id=service_id,
            provider=service_id,
            idempotency_key=idempotency_key,
            extra_data={
                "smartcard_number": smartcard_number,
                "variation_code": variation_code,
            },
            provider_callable=_call,
            paystack=paystack,
        )

    async def _resolve_variation_amount(
        self, service_id: str, variation_code: str
    ) -> Decimal:
        content = await self.vtpass.get_variation_codes(service_id)
        variations = content.get("varations", content.get("variations", []))

        for v in variations:
            if v.get("variation_code") == variation_code:
                return Decimal(str(v["variation_amount"]))

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Variation '{variation_code}' not found for provider '{service_id}'.",
        )
