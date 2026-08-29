import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, CableServiceIdPath, ChatIdPath
from app.schema.transaction import (
    CablePurchaseRequest,
    TransactionResponse,
    VerifySmartcardRequest,
)
from app.service.cable_service import CableService
from app.utils.libs.paystack.interfaces import PaystackOptions
from app.utils.libs.paystack.service import PaystackService
from app.utils.libs.vtpass.interfaces import VtpassOptions, VtpassVerifyResponse
from app.utils.libs.vtpass.service import VtpassService

router = APIRouter(prefix="/cable", tags=["Cable TV"])


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


def _get_cable_service(
    session: AsyncSession = Depends(get_db),
    vtpass: VtpassService = Depends(_get_vtpass),
) -> CableService:
    return CableService(session, vtpass)


@router.get(
    "/providers",
    response_model=ApiResponse[list[str]],
    status_code=status.HTTP_200_OK,
    summary="List cable providers",
    description="Returns all supported cable TV provider IDs.",
)
async def list_providers(
    service: CableService = Depends(_get_cable_service),
) -> ApiResponse[list[str]]:
    return ApiResponse(message="Providers", data=service.providers())


@router.get(
    "/{service_id}/variation-codes",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Get variation codes",
    description="Fetch available subscription packages for a cable provider from VTpass.",
)
async def get_variation_codes(
    service_id: CableServiceIdPath,
    service: CableService = Depends(_get_cable_service),
) -> ApiResponse[dict]:
    data = await service.get_variation_codes(service_id)
    return ApiResponse(message="Variation codes", data=data)


@router.post(
    "/verify-smartcard",
    response_model=ApiResponse[VtpassVerifyResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify smartcard number",
    description="Validate a cable TV smartcard number before purchase.",
)
async def verify_smartcard(
    payload: VerifySmartcardRequest,
    service: CableService = Depends(_get_cable_service),
) -> ApiResponse[VtpassVerifyResponse]:
    result = await service.verify_smartcard(
        payload.service_id, payload.smartcard_number
    )
    return ApiResponse(message="Smartcard verified", data=result)


@router.post(
    "/{chat_id}/buy",
    response_model=ApiResponse[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="Buy cable subscription",
    description="Subscribe to cable TV using a saved card.",
)
async def buy_cable(
    chat_id: ChatIdPath,
    payload: CablePurchaseRequest,
    service: CableService = Depends(_get_cable_service),
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
        chat_id=chat_id,
        service_id=payload.service_id,
        smartcard_number=payload.smartcard_number,
        variation_code=payload.variation_code,
        idempotency_key=payload.idempotency_key,
        paystack=paystack,
    )

    return ApiResponse(
        message="Cable subscription processed",
        data=TransactionResponse.model_validate(txn),
    )
