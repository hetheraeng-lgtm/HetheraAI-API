import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.controller.admin.deps import get_current_super_admin
from app.model.super_admin import SuperAdmin
from app.repository.super_admin_repository import SuperAdminRepository
from app.schema.common import ApiResponse
from app.schema.super_admin import (
    AdminLoginRequest,
    RefreshTokenRequest,
    SuperAdminCreate,
    SuperAdminResponse,
    SuperAdminUpdate,
    TokenResponse,
)
from app.service.super_admin_service import SuperAdminService
from app.utils.security import create_access_token

auth_router = APIRouter(prefix="/auth/admin", tags=["Super Admin Authentication"])
admin_router = APIRouter(prefix="/admin", tags=["Super Admin Management"])


def _get_admin_service(session: AsyncSession = Depends(get_db)) -> SuperAdminService:
    return SuperAdminService(session, SuperAdminRepository(session))


@auth_router.post(
    "/token",
    response_model=ApiResponse[TokenResponse],
    summary="Super admin login",
    description="OAuth2 password flow. Submit username + password, receive a Bearer JWT.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: SuperAdminService = Depends(_get_admin_service),
) -> ApiResponse[TokenResponse]:
    admin = await service.authenticate(form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ApiResponse(
        message="Login successful",
        data=TokenResponse(access_token=create_access_token(admin.id)),
    )


@auth_router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Admin login (dashboard)",
    description="JSON email + password login for the admin dashboard frontend. Returns an access token and a refresh token.",
)
async def login_json(
    payload: AdminLoginRequest,
    service: SuperAdminService = Depends(_get_admin_service),
) -> ApiResponse[TokenResponse]:
    access_token, refresh_token, expires_in = await service.login(
        payload.email, payload.password
    )
    return ApiResponse(
        message="Login successful",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        ),
    )


@auth_router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Refresh an admin access token",
    description="Exchanges a valid, unexpired refresh token for a new access/refresh token pair. Refresh tokens are single-use (rotated on each call).",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: SuperAdminService = Depends(_get_admin_service),
) -> ApiResponse[TokenResponse]:
    access_token, new_refresh_token, expires_in = await service.refresh(
        payload.refresh_token
    )
    return ApiResponse(
        message="Token refreshed successfully",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
        ),
    )


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin logout",
    description="Revokes the given refresh token so it can no longer be used to obtain new access tokens.",
)
async def logout(
    payload: RefreshTokenRequest,
    service: SuperAdminService = Depends(_get_admin_service),
) -> None:
    await service.logout(payload.refresh_token)


@auth_router.post(
    "/register",
    response_model=ApiResponse[SuperAdminResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register the (only) super admin",
    description=(
        "Creates the super admin account. Only one admin account may ever exist: "
        "this endpoint succeeds exactly once (enforced both by an application-level "
        "check and a DB-level unique constraint on the admin table), and returns "
        "409 Conflict on every subsequent call. Safe to leave unauthenticated since "
        "it is self-limiting."
    ),
)
async def register(
    payload: SuperAdminCreate,
    service: SuperAdminService = Depends(_get_admin_service),
) -> ApiResponse[SuperAdminResponse]:
    admin = await service.create(payload)
    return ApiResponse(
        message="Super admin registered successfully",
        data=SuperAdminResponse.model_validate(admin),
    )


@admin_router.get(
    "/me",
    response_model=ApiResponse[SuperAdminResponse],
    summary="Get current super admin profile",
)
async def get_me(
    current_admin: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[SuperAdminResponse]:
    return ApiResponse(
        message="Profile retrieved successfully",
        data=SuperAdminResponse.model_validate(current_admin),
    )


@admin_router.get(
    "",
    response_model=ApiResponse[list[SuperAdminResponse]],
    summary="List all super admins",
)
async def list_admins(
    skip: int = 0,
    limit: int = 100,
    service: SuperAdminService = Depends(_get_admin_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[list[SuperAdminResponse]]:
    admins = await service.list_admins(skip=skip, limit=limit)
    return ApiResponse(
        message="Super admins retrieved successfully",
        data=[SuperAdminResponse.model_validate(a) for a in admins],
    )


@admin_router.get(
    "/{admin_id}",
    response_model=ApiResponse[SuperAdminResponse],
    summary="Get super admin by ID",
)
async def get_admin(
    admin_id: uuid.UUID,
    service: SuperAdminService = Depends(_get_admin_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[SuperAdminResponse]:
    admin = await service.get_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Super admin not found"
        )
    return ApiResponse(
        message="Super admin retrieved successfully",
        data=SuperAdminResponse.model_validate(admin),
    )


@admin_router.patch(
    "/{admin_id}",
    response_model=ApiResponse[SuperAdminResponse],
    summary="Update super admin",
)
async def update_admin(
    admin_id: uuid.UUID,
    payload: SuperAdminUpdate,
    service: SuperAdminService = Depends(_get_admin_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[SuperAdminResponse]:
    admin = await service.update(admin_id, payload)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Super admin not found"
        )
    return ApiResponse(
        message="Super admin updated successfully",
        data=SuperAdminResponse.model_validate(admin),
    )


@admin_router.delete(
    "/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete super admin",
)
async def delete_admin(
    admin_id: uuid.UUID,
    service: SuperAdminService = Depends(_get_admin_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> None:
    deleted = await service.delete(admin_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Super admin not found"
        )
