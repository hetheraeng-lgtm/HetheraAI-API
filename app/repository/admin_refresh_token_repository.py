import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.admin_refresh_token import AdminRefreshToken
from app.repository.base import BaseRepository


class AdminRefreshTokenRepository(BaseRepository[AdminRefreshToken]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AdminRefreshToken, session)

    async def get_by_hash(self, token_hash: str) -> AdminRefreshToken | None:
        result = await self.session.execute(
            select(AdminRefreshToken).where(AdminRefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: AdminRefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        self.session.add(token)
        await self.session.flush()

    async def revoke_all_for_admin(self, admin_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AdminRefreshToken)
            .where(
                AdminRefreshToken.admin_id == admin_id,
                AdminRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.session.flush()
