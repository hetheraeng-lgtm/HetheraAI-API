import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import app_settings
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.vtpass import VtpassVerifyPurchaseBody
from app.utils.libs.vtpass.interfaces import VtpassOptions, VtpassWebhookResInterface
from app.utils.libs.vtpass.service import VtpassService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vtpass", tags=["VTPass"])


def _get_vtpass_service() -> VtpassService:
    return VtpassService(
        VtpassOptions(
            api_key=app_settings.VTPASS_API_KEY,
            secret_key=app_settings.VTPASS_SECRET_KEY,
            public_key=app_settings.VTPASS_PUBLIC_KEY,
            base_url=app_settings.VTPASS_BASE_URL,
        )
    )


@router.post("/webhook", summary="VTPass transaction webhook")
async def webhook(
    body: VtpassWebhookResInterface,
) -> dict:
    logger.info("VTPASS webhook received: %s", body)

    if body.type == "transaction-update":
        # background update — log service to be wired when available
        pass

    return {"response": "success"}


@router.post(
    "/verify-transaction",
    response_model=ApiResponse[dict],
    summary="Verify a VTPass transaction",
)
async def user_verify_transaction(
    body: VtpassVerifyPurchaseBody,
    vtpass: VtpassService = Depends(_get_vtpass_service),
) -> ApiResponse[dict]:
    res, err = await vtpass.verify_purchase(body.request_id)

    if not res or not res.content or not res.content.transactions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    return ApiResponse(
        message="Transaction verified",
        data={"status": res.content.transactions.status},
    )


@router.get(
    "/transactions",
    response_model=ApiResponse[dict],
    summary="List current user's VTPass transactions",
)
async def list_user_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
) -> ApiResponse[dict]:
    # vtpass_log_service.get_vtpass_transaction(user_id) to be wired when service is available
    return ApiResponse(message="VTPass transactions retrieved", data={})


@router.get(
    "/transactions/{transaction_id}",
    response_model=ApiResponse[dict],
    summary="Get a single VTPass transaction by ID",
)
async def get_user_transaction(
    transaction_id: UUID, chat_id: ChatIdPath
) -> ApiResponse[dict]:
    # vtpass_log_service.get_user_vtpass_transaction(transaction_id, user_id) to be wired
    return ApiResponse(message="VTPass transaction retrieved", data={})


@router.get(
    "/metadata/{transaction_id}",
    response_model=ApiResponse[dict],
    summary="Get buy-again payload for a past transaction",
)
async def get_buy_again_payload(
    transaction_id: str, chat_id: ChatIdPath
) -> ApiResponse[dict]:
    # vtpass_log_service.get_buy_again_payload(transaction_id, user_id) to be wired
    return ApiResponse(message="Buy-again payload retrieved", data={})
