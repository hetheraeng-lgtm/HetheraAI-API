from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

DateRangeOption = Literal["today", "7d", "30d", "custom"]
TimeseriesMetric = Literal["volume", "value", "revenue"]


class DashboardOverviewResponse(BaseModel):
    range: DateRangeOption
    start_date: datetime
    end_date: datetime
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    pending_transactions: int
    unknown_transactions: int
    total_transaction_value: Decimal
    total_revenue: Decimal
    total_customers: int
    active_customers: int
    success_rate: float
    # Percentage change vs. the immediately preceding period of equal length,
    # keyed by the metric name above (e.g. "total_transactions": 12.5 means
    # +12.5% vs. the previous period). Empty/omitted keys mean "no prior data".
    trends: dict[str, float]


class TimeseriesPoint(BaseModel):
    date: str
    value: Decimal


class TimeseriesResponse(BaseModel):
    metric: TimeseriesMetric
    points: list[TimeseriesPoint]


class BreakdownItem(BaseModel):
    label: str
    count: int
    value: Decimal


class BreakdownResponse(BaseModel):
    items: list[BreakdownItem]
