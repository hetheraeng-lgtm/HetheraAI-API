import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionType
from app.exceptions import ProviderValidationError
from app.model.transaction import Transaction
from app.schema.common import ELECTRICITY_PROVIDERS, ELECTRICITY_PROVIDER_LABELS
from app.service.transaction_service import TransactionService
from app.utils.libs.vtpass.interfaces import (
    BuyElectricityData,
    VerifyMeterNumberData,
    VtpassVerifyResponse,
)
from app.utils.libs.vtpass.service import VtpassService


class ElectricityService:

    def __init__(self, session: AsyncSession, vtpass: VtpassService) -> None:
        self.session = session
        self.vtpass = vtpass
        self.tx_service = TransactionService(session)

    def providers(self) -> dict[str, str]:
        return ELECTRICITY_PROVIDER_LABELS

    async def validate_meter(
        self, service_id: str, meter_number: str, meter_type: str
    ) -> VtpassVerifyResponse | None:
        return await self._verify_meter_number(service_id, meter_number, meter_type)

    async def purchase(
        self,
        user_id: uuid.UUID,
        chat_id: str,
        service_id: str,
        meter_number: str,
        variation_code: str,
        amount: Decimal,
        idempotency_key: str,
        paystack,
    ) -> Transaction:
        if service_id not in ELECTRICITY_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported electricity provider. Supported: {sorted(ELECTRICITY_PROVIDERS)}",
            )

        valid_amount, minimum_amount = await self._verify_purchase_amount(
            service_id, meter_number, variation_code, amount
        )

        if not valid_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum electricity purchase is ₦{minimum_amount:,.2f}.",
            )

        vtpass = self.vtpass

        async def _call():
            return await vtpass.buy_electricity(
                BuyElectricityData(
                    service_id=service_id,
                    phone=chat_id,
                    billers_code=meter_number,
                    variation_code=variation_code,
                    amount=str(amount),
                )
            )

        return await self.tx_service.execute_purchase(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.ELECTRICITY,
            service_id=service_id,
            provider=service_id,
            idempotency_key=idempotency_key,
            extra_data={
                "meter_number": meter_number,
                "variation_code": variation_code,
            },
            provider_callable=_call,
            paystack=paystack,
        )

    async def _verify_purchase_amount(
        self,
        service_id: str,
        meter_number: str,
        meter_type: str,
        amount: Decimal,
    ) -> tuple[bool, Decimal | None]:
        result = await self._verify_meter_number(service_id, meter_number, meter_type)

        if result is None or result.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to verify the electricity meter.",
            )

        minimum_amount = result.content.Min_Purchase_Amount

        if minimum_amount is None:
            return True, minimum_amount

        if amount < minimum_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The minimum purchase amount for {service_id} is "
                    f"₦{minimum_amount:,.2f}."
                ),
            )

        return True, minimum_amount

    async def _verify_meter_number(
        self,
        service_id: str,
        meter_number: str,
        meter_type: str,
    ) -> VtpassVerifyResponse | None:
        result, error = await self.vtpass.verify_merchant(
            VerifyMeterNumberData(
                service_id=service_id,
                billers_code=meter_number,
                type=meter_type,
            )
        )

        if error:
            raise ProviderValidationError(error)

        return result
