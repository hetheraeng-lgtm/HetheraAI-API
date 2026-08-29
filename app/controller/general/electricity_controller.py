from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.transaction import (
    ElectricityPurchaseRequest,
    TransactionResponse,
    VerifyMeterRequest,
)
from app.service.electricity_service import ElectricityService
from app.utils.libs.paystack.interfaces import PaystackOptions
from app.utils.libs.paystack.service import PaystackService
from app.utils.libs.vtpass.interfaces import VtpassOptions, VtpassVerifyResponse
from app.utils.libs.vtpass.service import VtpassService

router = APIRouter(prefix="/electricity", tags=["Electricity"])


def _get_vtpass() -> VtpassService:
    return VtpassService(
        VtpassOptions(
            api_key=app_settings.VTPASS_API_KEY,
            secret_key=app_settings.VTPASS_SECRET_KEY,
            public_key=app_settings.VTPASS_PUBLIC_KEY,
            base_url=app_settings.VTPASS_BASE_URL,
        )
    )


def _get_paystack() -> PaystackService:
    return PaystackService(
        PaystackOptions(
            base_url=app_settings.PAYSTACK_BASE_URL,
            secret_key=app_settings.PAYSTACK_SECRET_KEY,
            public_key=app_settings.PAYSTACK_PUBLIC_KEY,
            merchant_email=app_settings.PAYSTACK_MERCHANT_EMAIL,
        )
    )


def _get_electricity_service(
    session: AsyncSession = Depends(get_db),
    vtpass: VtpassService = Depends(_get_vtpass),
) -> ElectricityService:
    return ElectricityService(session, vtpass)


@router.get(
    "/providers",
    response_model=ApiResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="List electricity providers",
    description="Returns a mapping of provider abbreviation to service ID.",
)
async def list_providers(
    service: ElectricityService = Depends(_get_electricity_service),
) -> ApiResponse[dict[str, str]]:
    return ApiResponse(message="Providers", data=service.providers())


@router.post(
    "/verify-meter",
    response_model=ApiResponse[VtpassVerifyResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify meter number",
    description="Validate an electricity meter number before purchase.",
)
async def verify_meter(
    payload: VerifyMeterRequest,
    service: ElectricityService = Depends(_get_electricity_service),
) -> ApiResponse[VtpassVerifyResponse]:
    result = await service.validate_meter(
        payload.service_id, payload.meter_number, payload.meter_type
    )
    return ApiResponse(message="Meter verified", data=result)


@router.post(
    "/{chat_id}/buy",
    response_model=ApiResponse[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="Buy electricity",
    description="Purchase electricity units using a saved card.",
)
async def buy_electricity(
    chat_id: ChatIdPath,
    payload: ElectricityPurchaseRequest,
    service: ElectricityService = Depends(_get_electricity_service),
    paystack: PaystackService = Depends(_get_paystack),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TransactionResponse]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    txn = await service.purchase(
        user_id=user.id,
        chat_id=user.chat_id,
        service_id=payload.service_id,
        meter_number=payload.meter_number,
        variation_code=payload.meter_type,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
        paystack=paystack,
    )
    return ApiResponse(
        message="Electricity purchase processed",
        data=TransactionResponse.model_validate(txn),
    )
