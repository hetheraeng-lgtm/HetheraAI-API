from pydantic import BaseModel
from typing import Optional


class VtpassVerifyPurchaseBody(BaseModel):
    request_id: str


class VtpassPaginationQuery(BaseModel):
    page: int = 1
    limit: int = 20
    search: Optional[str] = None


class VtpassStatsQuery(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
