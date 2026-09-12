import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.model.admin_refresh_token import AdminRefreshToken
from app.model.super_admin import SuperAdmin
from app.repository.admin_refresh_token_repository import AdminRefreshTokenRepository
from app.repository.super_admin_repository import SuperAdminRepository
from app.schema.super_admin import SuperAdminCreate, SuperAdminUpdate
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


class SuperAdminService:

    def __init__(
        self,
        session: AsyncSession,
        repo: SuperAdminRepository,
        refresh_repo: AdminRefreshTokenRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo
        self.refresh_repo = refresh_repo or AdminRefreshTokenRepository(session)

    async def authenticate(self, username: str, password: str) -> SuperAdmin | None:
        admin = await self.repo.get_by_username(username)

        if not admin or not verify_password(password, admin.hashed_password):
            return None

        return admin

    async def authenticate_by_email(self, email: str, password: str) -> SuperAdmin | None:
        admin = await self.repo.get_by_email(email)

        if not admin or not admin.is_active or not verify_password(password, admin.hashed_password):
            return None

        return admin

    async def create(self, data: SuperAdminCreate) -> SuperAdmin:
        # App-level check first for a clean, common-case error message; the
        # DB's unique constraint on SuperAdmin.singleton (see app/model) is
        # the authoritative backstop against a race between two concurrent
        # first-registration requests.
        existing = await self.repo.get_all(limit=1)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An admin account already exists. Only one admin account is permitted.",
            )

        admin = SuperAdmin(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
        )

        try:
            await self.repo.add(admin)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An admin account already exists. Only one admin account is permitted.",
            )

        return admin

    def _issue_tokens(self, admin: SuperAdmin) -> tuple[str, str, int]:
        access_token = create_access_token(admin.id)
        raw_refresh_token = create_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=app_settings.REFRESH_TOKEN_EXPIRES_DAYS
        )
        self.session.add(
            AdminRefreshToken(
                admin_id=admin.id,
                token_hash=hash_token(raw_refresh_token),
                expires_at=expires_at,
            )
        )
        return access_token, raw_refresh_token, app_settings.ACCESS_TOKEN_EXPIRES

    async def login(self, email: str, password: str) -> tuple[str, str, int]:
        admin = await self.authenticate_by_email(email, password)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        tokens = self._issue_tokens(admin)
        await self.session.commit()
        return tokens

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str, int]:
        invalid = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

        token = await self.refresh_repo.get_by_hash(hash_token(raw_refresh_token))
        expires_at = (
            token.expires_at.replace(tzinfo=timezone.utc)
            if token and token.expires_at.tzinfo is None
            else (token.expires_at if token else None)
        )
        if (
            not token
            or token.revoked_at is not None
            or expires_at < datetime.now(timezone.utc)
        ):
            raise invalid

        admin = await self.repo.get_by_id(token.admin_id)
        if not admin or not admin.is_active:
            raise invalid

        # Rotate: revoke the used token and issue a brand new pair.
        await self.refresh_repo.revoke(token)
        tokens = self._issue_tokens(admin)
        await self.session.commit()
        return tokens

    async def logout(self, raw_refresh_token: str) -> None:
        token = await self.refresh_repo.get_by_hash(hash_token(raw_refresh_token))
        if token and token.revoked_at is None:
            await self.refresh_repo.revoke(token)
            await self.session.commit()

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
