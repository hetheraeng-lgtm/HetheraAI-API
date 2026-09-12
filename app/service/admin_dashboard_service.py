from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.transaction import TransactionStatus
from app.model.transaction import Transaction
from app.model.user import User
from app.schema.admin_dashboard import (
    BreakdownItem,
    BreakdownResponse,
    DashboardOverviewResponse,
    DateRangeOption,
    TimeseriesMetric,
    TimeseriesPoint,
    TimeseriesResponse,
)


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def resolve_range(
    range_: DateRangeOption,
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)

    if range_ == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range_ == "7d":
        return now - timedelta(days=7), now
    if range_ == "30d":
        return now - timedelta(days=30), now

    if range_ == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date are required for a custom range",
            )
        start, end = _ensure_aware(start_date), _ensure_aware(end_date)
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before end_date",
            )
        return start, end

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range")


class AdminDashboardService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _core_metrics(self, start: datetime, end: datetime) -> dict:
        status_counts_stmt = (
            select(Transaction.status, func.count(Transaction.id))
            .where(Transaction.created_at.between(start, end))
            .group_by(Transaction.status)
        )
        result = await self.session.execute(status_counts_stmt)
        counts_by_status = dict(result.all())

        successful = counts_by_status.get(TransactionStatus.SUCCESSFUL, 0)
        failed = counts_by_status.get(TransactionStatus.FAILED, 0)
        pending = counts_by_status.get(TransactionStatus.INITIATED, 0) + counts_by_status.get(
            TransactionStatus.PROCESSING, 0
        )
        unknown = counts_by_status.get(TransactionStatus.UNKNOWN, 0)
        total = sum(counts_by_status.values())

        value_revenue_stmt = select(
            func.coalesce(
                func.sum(
                    case((Transaction.status == TransactionStatus.SUCCESSFUL, Transaction.amount), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.status == TransactionStatus.SUCCESSFUL, Transaction.profit_loss),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(func.distinct(Transaction.user_id)),
        ).where(Transaction.created_at.between(start, end))
        value_row = (await self.session.execute(value_revenue_stmt)).one()
        total_value, total_revenue, active_customers = value_row

        success_rate = (successful / (successful + failed) * 100) if (successful + failed) else 0.0

        return {
            "total_transactions": total,
            "successful_transactions": successful,
            "failed_transactions": failed,
            "pending_transactions": pending,
            "unknown_transactions": unknown,
            "total_transaction_value": Decimal(total_value or 0),
            "total_revenue": Decimal(total_revenue or 0),
            "active_customers": active_customers or 0,
            "success_rate": round(success_rate, 2),
        }

    @staticmethod
    def _trend(current: float, previous: float) -> float:
        if previous:
            return round((current - previous) / previous * 100, 2)
        return 100.0 if current else 0.0

    async def get_overview(
        self,
        range_: DateRangeOption,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> DashboardOverviewResponse:
        start, end = resolve_range(range_, start_date, end_date)
        period_length = end - start
        prev_start, prev_end = start - period_length, start

        current = await self._core_metrics(start, end)
        previous = await self._core_metrics(prev_start, prev_end)

        total_customers = (await self.session.execute(select(func.count(User.id)))).scalar_one()

        trends = {
            key: self._trend(float(current[key]), float(previous[key]))
            for key in (
                "total_transactions",
                "total_transaction_value",
                "total_revenue",
                "active_customers",
                "success_rate",
            )
        }

        return DashboardOverviewResponse(
            range=range_,
            start_date=start,
            end_date=end,
            total_customers=total_customers,
            trends=trends,
            **current,
        )

    async def get_timeseries(
        self,
        metric: TimeseriesMetric,
        range_: DateRangeOption,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> TimeseriesResponse:
        start, end = resolve_range(range_, start_date, end_date)
        day = func.date(Transaction.created_at)

        if metric == "volume":
            value_expr = func.count(Transaction.id)
        elif metric == "value":
            value_expr = func.coalesce(
                func.sum(
                    case((Transaction.status == TransactionStatus.SUCCESSFUL, Transaction.amount), else_=0)
                ),
                0,
            )
        else:  # revenue
            value_expr = func.coalesce(
                func.sum(
                    case(
                        (Transaction.status == TransactionStatus.SUCCESSFUL, Transaction.profit_loss),
                        else_=0,
                    )
                ),
                0,
            )

        stmt = (
            select(day.label("day"), value_expr.label("value"))
            .where(Transaction.created_at.between(start, end))
            .group_by(day)
            .order_by(day)
        )
        rows = (await self.session.execute(stmt)).all()

        points = [TimeseriesPoint(date=str(r.day), value=Decimal(r.value or 0)) for r in rows]
        return TimeseriesResponse(metric=metric, points=points)

    async def _breakdown(
        self,
        group_col,
        range_: DateRangeOption,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> BreakdownResponse:
        start, end = resolve_range(range_, start_date, end_date)

        stmt = (
            select(
                group_col.label("label"),
                func.count(Transaction.id).label("count"),
                func.coalesce(
                    func.sum(
                        case((Transaction.status == TransactionStatus.SUCCESSFUL, Transaction.amount), else_=0)
                    ),
                    0,
                ).label("value"),
            )
            .where(Transaction.created_at.between(start, end))
            .group_by(group_col)
            .order_by(func.count(Transaction.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()

        return BreakdownResponse(
            items=[
                BreakdownItem(label=str(r.label), count=r.count, value=Decimal(r.value or 0))
                for r in rows
            ]
        )

    async def get_by_type(
        self, range_: DateRangeOption, start_date: datetime | None, end_date: datetime | None
    ) -> BreakdownResponse:
        return await self._breakdown(Transaction.type, range_, start_date, end_date)

    async def get_by_provider(
        self, range_: DateRangeOption, start_date: datetime | None, end_date: datetime | None
    ) -> BreakdownResponse:
        return await self._breakdown(Transaction.provider, range_, start_date, end_date)
