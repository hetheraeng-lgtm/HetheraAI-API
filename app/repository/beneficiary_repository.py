import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.beneficiary import Beneficiary
from app.repository.base import BaseRepository


class BeneficiaryRepository(BaseRepository[Beneficiary]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Beneficiary, session)

    async def get_user_beneficiaries(
        self,
        user_id: uuid.UUID,
        service_type: str | None = None,
    ) -> list[Beneficiary]:
        query = select(Beneficiary).where(
            Beneficiary.user_id == user_id,
            Beneficiary.is_active == True,
        )
        if service_type:
            query = query.where(Beneficiary.service_type == service_type)
        result = await self.session.execute(query.order_by(Beneficiary.name))
        return list(result.scalars().all())

    async def get_user_beneficiary(
        self, user_id: uuid.UUID, beneficiary_id: uuid.UUID
    ) -> Beneficiary | None:
        result = await self.session.execute(
            select(Beneficiary).where(
                Beneficiary.id == beneficiary_id,
                Beneficiary.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
