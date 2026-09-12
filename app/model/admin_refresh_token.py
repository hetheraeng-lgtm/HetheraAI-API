import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base, TimestampMixin


class AdminRefreshToken(Base, TimestampMixin):
    __tablename__ = "admin_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("super_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 hex digest of the raw refresh token — the usable secret itself
    # is never stored, only sent to the client once at issuance.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
