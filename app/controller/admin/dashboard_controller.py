from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.controller.admin.deps import get_current_super_admin
from app.schema.admin_dashboard import (
    BreakdownResponse,
    DashboardOverviewResponse,
    DateRangeOption,
    TimeseriesMetric,
    TimeseriesResponse,
)
from app.schema.common import ApiResponse
from app.service.admin_dashboard_service import AdminDashboardService

router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin Dashboard"],
    dependencies=[Depends(get_current_super_admin)],
)


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminDashboardService:
    return AdminDashboardService(session)


@router.get(
    "/overview",
    response_model=ApiResponse[DashboardOverviewResponse],
    summary="Dashboard summary metrics",
)
async def get_overview(
    range: DateRangeOption = Query("30d"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: AdminDashboardService = Depends(_get_service),
) -> ApiResponse[DashboardOverviewResponse]:
    data = await service.get_overview(range, start_date, end_date)
    return ApiResponse(message="Dashboard overview retrieved successfully", data=data)


@router.get(
    "/timeseries",
    response_model=ApiResponse[TimeseriesResponse],
    summary="Transaction metric over time",
)
async def get_timeseries(
    metric: TimeseriesMetric = Query("volume"),
    range: DateRangeOption = Query("30d"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: AdminDashboardService = Depends(_get_service),
) -> ApiResponse[TimeseriesResponse]:
    data = await service.get_timeseries(metric, range, start_date, end_date)
    return ApiResponse(message="Timeseries retrieved successfully", data=data)


@router.get(
    "/by-type",
    response_model=ApiResponse[BreakdownResponse],
    summary="Transactions broken down by service category",
)
async def get_by_type(
    range: DateRangeOption = Query("30d"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: AdminDashboardService = Depends(_get_service),
) -> ApiResponse[BreakdownResponse]:
    data = await service.get_by_type(range, start_date, end_date)
    return ApiResponse(message="Breakdown retrieved successfully", data=data)


@router.get(
    "/by-provider",
    response_model=ApiResponse[BreakdownResponse],
    summary="Transactions broken down by provider",
)
async def get_by_provider(
    range: DateRangeOption = Query("30d"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: AdminDashboardService = Depends(_get_service),
) -> ApiResponse[BreakdownResponse]:
    data = await service.get_by_provider(range, start_date, end_date)
    return ApiResponse(message="Breakdown retrieved successfully", data=data)
