from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.super_admin import SuperAdmin
from app.repository.base import BaseRepository


class SuperAdminRepository(BaseRepository[SuperAdmin]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SuperAdmin, session)

    async def get_by_username(self, username: str) -> SuperAdmin | None:
        result = await self.session.execute(
            select(SuperAdmin).where(SuperAdmin.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> SuperAdmin | None:
        result = await self.session.execute(
            select(SuperAdmin).where(SuperAdmin.email == email)
        )
        return result.scalar_one_or_none()
