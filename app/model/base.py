from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

WAT = ZoneInfo("Africa/Lagos")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        default=lambda: datetime.now(WAT),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        default=lambda: datetime.now(WAT),
        onupdate=lambda: datetime.now(WAT),
    )
