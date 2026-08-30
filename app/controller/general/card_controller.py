from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.transaction import (
    CardInitializeRequest,
    CardInitializeResponse,
    CardResponse,
)
from app.service.card_service import CardService
from app.utils.libs.paystack.interfaces import PaystackOptions
from app.utils.libs.paystack.service import PaystackService

router = APIRouter(prefix="/cards", tags=["Cards"])


def _get_paystack() -> PaystackService:
    return PaystackService(
        PaystackOptions(
            base_url=app_settings.PAYSTACK_BASE_URL,
            secret_key=app_settings.PAYSTACK_SECRET_KEY,
            public_key=app_settings.PAYSTACK_PUBLIC_KEY,
            merchant_email=app_settings.PAYSTACK_MERCHANT_EMAIL,
        )
    )


def _get_card_service(
    session: AsyncSession = Depends(get_db),
    paystack: PaystackService = Depends(_get_paystack),
) -> CardService:
    return CardService(session, paystack)


@router.post(
    "/{chat_id}/initialize",
    response_model=ApiResponse[CardInitializeResponse],
    status_code=status.HTTP_200_OK,
    summary="Initialize card authorization",
    description="Generate a Paystack authorization URL. The user visits it to save a card.",
)
async def initialize_card(
    chat_id: ChatIdPath,
    payload: CardInitializeRequest,
    service: CardService = Depends(_get_card_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[CardInitializeResponse]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    result = await service.initialize_card_authorization(
        user_id=user.id,
        email=payload.email,
        callback_url=payload.callback_url,
    )

    return ApiResponse(
        message="Card authorization URL generated",
        data=CardInitializeResponse(**result),
    )


@router.get(
    "/{chat_id}",
    response_model=ApiResponse[CardResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get card",
    description="Get the saved card for a user.",
)
async def get_card(
    chat_id: ChatIdPath,
    service: CardService = Depends(_get_card_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[CardResponse | None]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    card = await service.get_card(user.id)

    return ApiResponse(
        message="Card retrieved",
        data=CardResponse.model_validate(card) if card else None,
    )


@router.delete(
    "/{chat_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete card",
    description="Remove the saved card.",
)
async def delete_card(
    chat_id: ChatIdPath,
    service: CardService = Depends(_get_card_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await service.delete_card(user.id)

    return ApiResponse(message="Card removed")
