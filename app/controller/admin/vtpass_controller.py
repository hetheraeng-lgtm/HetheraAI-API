import logging
import os
import uuid
from typing import Optional
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from app.config import app_settings
from app.controller.admin.deps import get_current_super_admin
from app.model.super_admin import SuperAdmin
from app.schema.common import ApiResponse
from app.schema.vtpass import VtpassVerifyPurchaseBody
from app.utils.libs.vtpass.interfaces import VtpassOptions
from app.utils.libs.vtpass.service import VtpassService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vtpass", tags=["VTPass"])
user_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/users/token")


def _get_vtpass_service() -> VtpassService:
    return VtpassService(
        VtpassOptions(
            api_key=app_settings.VTPASS_API_KEY,
            secret_key=app_settings.VTPASS_SECRET_KEY,
            public_key=app_settings.VTPASS_PUBLIC_KEY,
            base_url=app_settings.VTPASS_BASE_URL,
        )
    )


@router.get(
    "/admin/balance",
    response_model=ApiResponse[dict],
    summary="Get VTPass wallet balance",
)
async def vtpass_balance(
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[dict]:
    # vtpass.get_balance() to be wired when service method is available
    return ApiResponse(message="VTPass balance retrieved", data={})


@router.get(
    "/admin/stats",
    response_model=ApiResponse[dict],
    summary="Get VTPass transaction statistics",
)
async def vtpass_stats(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[dict]:
    # vtpass_log_service.vtpass_stats() to be wired when service is available
    return ApiResponse(message="VTPass stats retrieved", data={})


@router.post(
    "/admin/verify-transaction",
    response_model=ApiResponse[dict],
    summary="Admin: verify a VTPass transaction",
)
async def admin_verify_transaction(
    body: VtpassVerifyPurchaseBody,
    vtpass: VtpassService = Depends(_get_vtpass_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[dict]:
    res, err = await vtpass.verify_purchase(body.request_id)

    if not res or not res.content or not res.content.transactions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    return ApiResponse(
        message="Transaction verified",
        data={"status": res.content.transactions.status},
    )


@router.get(
    "/admin/transactions",
    response_model=ApiResponse[dict],
    summary="Admin: list all VTPass transactions",
)
async def admin_list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[dict]:
    # vtpass_log_service.get_vtpass_transaction() to be wired when service is available
    return ApiResponse(message="VTPass transactions retrieved", data={})


@router.get(
    "/admin/transactions/{transaction_id}",
    response_model=ApiResponse[dict],
    summary="Get a single VTPass transaction by ID",
)
async def get_user_transaction(
    transaction_id: UUID,
    user_id: UUID,
) -> ApiResponse[dict]:
    # vtpass_log_service.get_user_vtpass_transaction(transaction_id, user_id) to be wired
    return ApiResponse(message="VTPass transaction retrieved", data={})


@router.get(
    "/admin/metadata/{transaction_id}",
    response_model=ApiResponse[dict],
    summary="Get buy-again payload for a past transaction",
)
async def get_buy_again_payload(
    transaction_id: str,
    user_id: UUID,
) -> ApiResponse[dict]:
    # vtpass_log_service.get_buy_again_payload(transaction_id, user_id) to be wired
    return ApiResponse(message="Buy-again payload retrieved", data={})
