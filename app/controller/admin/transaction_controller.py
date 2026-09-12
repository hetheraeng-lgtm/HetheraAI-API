import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.controller.admin.deps import get_current_super_admin
from app.enums.transaction import TransactionStatus, TransactionType
from app.schema.admin_transaction import TransactionDetailResponse, TransactionListResponse
from app.schema.common import ApiResponse
from app.service.admin_transaction_service import AdminTransactionService

router = APIRouter(
    prefix="/admin/transactions",
    tags=["Admin Transactions"],
    dependencies=[Depends(get_current_super_admin)],
)


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminTransactionService:
    return AdminTransactionService(session)


@router.get(
    "",
    response_model=ApiResponse[TransactionListResponse],
    summary="List transactions (paginated, filterable)",
)
async def list_transactions(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None),
    status: TransactionStatus | None = Query(None),
    type: TransactionType | None = Query(None),
    provider: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    min_amount: Decimal | None = Query(None),
    max_amount: Decimal | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    service: AdminTransactionService = Depends(_get_service),
) -> ApiResponse[TransactionListResponse]:
    data = await service.list_transactions(
        page=page,
        size=size,
        search=search,
        status_=status,
        type_=type,
        provider=provider,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        user_id=user_id,
    )
    return ApiResponse(message="Transactions retrieved successfully", data=data)


@router.get(
    "/{reference}",
    response_model=ApiResponse[TransactionDetailResponse],
    summary="Get full transaction detail",
)
async def get_transaction(
    reference: str,
    service: AdminTransactionService = Depends(_get_service),
) -> ApiResponse[TransactionDetailResponse]:
    data = await service.get_detail(reference)
    return ApiResponse(message="Transaction retrieved successfully", data=data)
