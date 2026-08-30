import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionType
from app.model.transaction import Transaction
from app.schema.common import DATA_PROVIDERS
from app.service.transaction_service import TransactionService
from app.utils.libs.vtpass.interfaces import BuyMobileDataData
from app.utils.libs.vtpass.service import VtpassService
from app.utils.phone import validate_nigerian_phone


class MobileDataService:

    def __init__(self, session: AsyncSession, vtpass: VtpassService) -> None:
        self.session = session
        self.vtpass = vtpass
        self.tx_service = TransactionService(session)

    def providers(self) -> list[str]:
        return sorted(DATA_PROVIDERS)

    async def get_variation_codes(self, service_id: str) -> dict:
        if service_id not in DATA_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported data provider. Supported: {sorted(DATA_PROVIDERS)}",
            )
        return await self.vtpass.get_variation_codes(service_id)

    async def purchase(
        self,
        user_id: uuid.UUID,
        service_id: str,
        phone: str,
        variation_code: str,
        idempotency_key: str,
        paystack,
    ) -> Transaction:
        if service_id not in DATA_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported data provider. Supported: {sorted(DATA_PROVIDERS)}",
            )
        phone = validate_nigerian_phone(phone)
        if not variation_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="variation_code is required.",
            )

        # Amount is derived from the VTpass variation — client price is ignored
        amount = await self._resolve_variation_amount(service_id, variation_code)
        vtpass = self.vtpass

        async def _call():
            return await vtpass.buy_mobile_data(
                BuyMobileDataData(
                    service_id=service_id,
                    phone=phone,
                    billers_code=phone,
                    variation_code=variation_code,
                )
            )

        return await self.tx_service.execute_purchase(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.MOBILE_DATA,
            service_id=service_id,
            provider=service_id,
            idempotency_key=idempotency_key,
            extra_data={"phone": phone, "variation_code": variation_code},
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
