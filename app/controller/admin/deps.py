import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.model.super_admin import SuperAdmin
from app.repository.super_admin_repository import SuperAdminRepository
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/admin/token")


async def get_current_super_admin(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> SuperAdmin:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        admin_id = uuid.UUID(decode_access_token(token))
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_exc

    repo = SuperAdminRepository(session)
    admin = await repo.get_by_id(admin_id)

    if not admin or not admin.is_active:
        raise credentials_exc

    return admin
