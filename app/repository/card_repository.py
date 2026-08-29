import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user_card import UserCard
from app.repository.base import BaseRepository


class CardRepository(BaseRepository[UserCard]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserCard, session)

    async def get_user_card(self, user_id: uuid.UUID) -> UserCard | None:
        result = await self.session.execute(
            select(UserCard).where(UserCard.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_authorization_code(
        self, user_id: uuid.UUID, authorization_code: str
    ) -> UserCard | None:
        result = await self.session.execute(
            select(UserCard).where(
                UserCard.user_id == user_id,
                UserCard.authorization_code == authorization_code,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_user_id(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(UserCard).where(UserCard.user_id == user_id))
