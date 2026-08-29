import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.transaction import AirtimePurchaseRequest, TransactionResponse
from app.service.airtime_service import AirtimeService
from app.utils.libs.paystack.interfaces import PaystackOptions
from app.utils.libs.paystack.service import PaystackService
from app.utils.libs.vtpass.interfaces import VtpassOptions
from app.utils.libs.vtpass.service import VtpassService

router = APIRouter(prefix="/airtime", tags=["Airtime"])


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


def _get_airtime_service(
    session: AsyncSession = Depends(get_db),
    vtpass: VtpassService = Depends(_get_vtpass),
) -> AirtimeService:
    return AirtimeService(session, vtpass)


@router.get(
    "/providers",
    response_model=ApiResponse[list[str]],
    status_code=status.HTTP_200_OK,
    summary="List airtime providers",
    description="Returns all supported airtime provider IDs.",
)
async def list_providers(
    service: AirtimeService = Depends(_get_airtime_service),
) -> ApiResponse[list[str]]:
    return ApiResponse(message="Providers", data=service.providers())


@router.post(
    "/{chat_id}/buy",
    response_model=ApiResponse[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="Buy airtime",
    description="Purchase airtime for the given phone number using a saved card.",
)
async def buy_airtime(
    chat_id: ChatIdPath,
    payload: AirtimePurchaseRequest,
    service: AirtimeService = Depends(_get_airtime_service),
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
        service_id=payload.service_id,
        phone=payload.phone,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
        paystack=paystack,
    )

    return ApiResponse(
        message="Airtime purchase processed",
        data=TransactionResponse.model_validate(txn),
    )
