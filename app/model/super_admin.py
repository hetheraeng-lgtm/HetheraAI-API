import uuid

from sqlalchemy import Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base, TimestampMixin


class SuperAdmin(Base, TimestampMixin):
    __tablename__ = "super_admins"
    __table_args__ = (
        # Fixed-value column with a unique constraint: a classic Postgres
        # singleton-table pattern. Every row must have singleton=1, so the
        # unique constraint makes "at most one admin can ever exist" a real
        # DB-level guarantee (immune to races), not just an app-level check.
        UniqueConstraint("singleton", name="uq_super_admins_singleton"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    singleton: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
