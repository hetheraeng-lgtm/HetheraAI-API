import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.beneficiary import Beneficiary
from app.repository.beneficiary_repository import BeneficiaryRepository


class BeneficiaryService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BeneficiaryRepository(session)

    async def list_beneficiaries(
        self, user_id: uuid.UUID, service_type: str | None = None
    ) -> list[Beneficiary]:
        return await self.repo.get_user_beneficiaries(user_id, service_type)

    async def add_beneficiary(
        self,
        user_id: uuid.UUID,
        name: str,
        identifier: str,
        service_type: str,
        service_id: str,
    ) -> Beneficiary:
        beneficiary = Beneficiary(
            user_id=user_id,
            name=name.strip(),
            identifier=identifier.strip(),
            service_type=service_type,
            service_id=service_id,
        )

        await self.repo.add(beneficiary)
        await self.session.commit()
        await self.session.refresh(beneficiary)

        return beneficiary

    async def update_beneficiary(
        self,
        user_id: uuid.UUID,
        beneficiary_id: uuid.UUID,
        name: str | None = None,
        identifier: str | None = None,
        service_id: str | None = None,
    ) -> Beneficiary:
        b = await self._require(user_id, beneficiary_id)

        if name is not None:
            b.name = name.strip()

        if identifier is not None:
            b.identifier = identifier.strip()

        if service_id is not None:
            b.service_id = service_id

        self.session.add(b)

        await self.session.commit()
        await self.session.refresh(b)

        return b

    async def delete_beneficiary(
        self, user_id: uuid.UUID, beneficiary_id: uuid.UUID
    ) -> None:
        b = await self._require(user_id, beneficiary_id)
        b.is_active = False
        self.session.add(b)
        await self.session.commit()

    async def _require(
        self, user_id: uuid.UUID, beneficiary_id: uuid.UUID
    ) -> Beneficiary:
        b = await self.repo.get_user_beneficiary(user_id, beneficiary_id)

        if not b or not b.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Beneficiary not found"
            )

        return b
