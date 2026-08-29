from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.controller.admin.deps import get_current_super_admin
from app.model.super_admin import SuperAdmin
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.user import UserResponse, UserUpdate
from app.service.user_service import UserService

router = APIRouter(prefix="/admin/users", tags=["User Management"])


def _get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session, UserRepository(session))


@router.get(
    "",
    response_model=ApiResponse[list[UserResponse]],
    summary="List all users",
    description="Returns a paginated list of all registered users.",
)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(_get_user_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[list[UserResponse]]:
    users = await service.list_users(skip=skip, limit=limit)
    return ApiResponse(
        message="Users retrieved successfully",
        data=[UserResponse.model_validate(u) for u in users],
    )


@router.get(
    "/{chat_id}",
    response_model=ApiResponse[UserResponse],
    summary="Get user by chat ID",
    description="Fetch a single user by their chat ID.",
)
async def get_user(
    chat_id: ChatIdPath,
    service: UserService = Depends(_get_user_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[UserResponse]:
    user = await service.get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return ApiResponse(
        message="User retrieved successfully", data=UserResponse.model_validate(user)
    )


@router.patch(
    "/{chat_id}",
    response_model=ApiResponse[UserResponse],
    summary="Update user",
    description="Update user fields (e.g. active status).",
)
async def update_user(
    chat_id: ChatIdPath,
    payload: UserUpdate,
    service: UserService = Depends(_get_user_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> ApiResponse[UserResponse]:
    user = await service.update_user(chat_id, payload)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return ApiResponse(
        message="User updated successfully", data=UserResponse.model_validate(user)
    )


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete user",
    description="Permanently remove a user record.",
)
async def delete_user(
    chat_id: ChatIdPath,
    service: UserService = Depends(_get_user_service),
    _: SuperAdmin = Depends(get_current_super_admin),
) -> None:
    deleted = await service.delete_user(chat_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
