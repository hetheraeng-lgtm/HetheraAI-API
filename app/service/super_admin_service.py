import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.model.super_admin import SuperAdmin
from app.repository.super_admin_repository import SuperAdminRepository
from app.schema.super_admin import SuperAdminCreate, SuperAdminUpdate
from app.utils.security import hash_password, verify_password


class SuperAdminService:

    def __init__(self, session: AsyncSession, repo: SuperAdminRepository) -> None:
        self.session = session
        self.repo = repo

    async def authenticate(self, username: str, password: str) -> SuperAdmin | None:
        admin = await self.repo.get_by_username(username)

        if not admin or not verify_password(password, admin.hashed_password):
            return None

        return admin

    async def create(self, data: SuperAdminCreate) -> SuperAdmin:
        admin = SuperAdmin(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
        )

        await self.repo.add(admin)
        await self.session.commit()

        return admin

    async def get_by_id(self, admin_id: uuid.UUID) -> SuperAdmin | None:
        return await self.repo.get_by_id(admin_id)

    async def list_admins(self, *, skip: int = 0, limit: int = 100) -> list[SuperAdmin]:
        return await self.repo.get_all(skip=skip, limit=limit)

    async def update(
        self, admin_id: uuid.UUID, data: SuperAdminUpdate
    ) -> SuperAdmin | None:
        admin = await self.repo.get_by_id(admin_id)

        if not admin:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        if not update_data:
            return admin

        await self.repo.update(admin, update_data)
        await self.session.commit()

        return admin

    async def delete(self, admin_id: uuid.UUID) -> bool:
        admin = await self.repo.get_by_id(admin_id)

        if not admin:
            return False

        await self.repo.delete(admin)
        await self.session.commit()

        return True
