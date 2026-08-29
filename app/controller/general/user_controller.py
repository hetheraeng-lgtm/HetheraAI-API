from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.user import (
    EnableAccountRequest,
    ResetPinRequest,
    SetPinRequest,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    VerifyPinRequest,
    VerifyPinResponse,
)
from app.service.user_service import UserService

auth_router = APIRouter(prefix="/auth/users", tags=["User Authentication"])


def _get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session, UserRepository(session))


@auth_router.post(
    "",
    response_model=ApiResponse[UserCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user by providing a chat_id and chat_type. Returns the identifier and whether this is a new registration.",
)
async def register_user(
    payload: UserCreateRequest,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[UserCreateResponse]:
    user, is_new = await service.register(payload)
    msg = "User registered successfully" if is_new else "User already exists"
    return ApiResponse(
        message=msg, data=UserCreateResponse(identifier=user.id, is_new=is_new)
    )


@auth_router.post(
    "/enable",
    response_model=ApiResponse[UserResponse],
    summary="Re-enable a disabled account",
    description="Re-enable a disabled account by providing the chat_id and current transaction PIN.",
)
async def enable_account(
    payload: EnableAccountRequest,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[UserResponse]:
    user = await service.enable_account(payload)
    return ApiResponse(
        message="Account enabled successfully", data=UserResponse.model_validate(user)
    )


@auth_router.post(
    "/{chat_id}/pin",
    response_model=ApiResponse[UserResponse],
    summary="Set transaction PIN",
    description="Set the 8-digit transaction PIN for the user. Can only be set once; use the reset endpoint to change it.",
)
async def set_pin(
    chat_id: ChatIdPath,
    payload: SetPinRequest,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[UserResponse]:
    user = await service.set_pin(chat_id, payload)
    return ApiResponse(
        message="Transaction PIN set successfully",
        data=UserResponse.model_validate(user),
    )


@auth_router.put(
    "/{chat_id}/pin",
    response_model=ApiResponse[UserResponse],
    summary="Reset transaction PIN",
    description="Change the transaction PIN by providing the current PIN and a new 8-digit PIN. The new PIN must differ from the old one. Allowed even while PIN-locked; clears all lockout state on success.",
)
async def reset_pin(
    chat_id: ChatIdPath,
    payload: ResetPinRequest,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[UserResponse]:
    user = await service.reset_pin(chat_id, payload)
    return ApiResponse(
        message="Transaction PIN reset successfully",
        data=UserResponse.model_validate(user),
    )


@auth_router.post(
    "/{chat_id}/verify-pin",
    response_model=ApiResponse[VerifyPinResponse],
    summary="Verify transaction PIN",
    description="Verify a user's transaction PIN. After 3 failed attempts the account is locked for 15 minutes. Each subsequent lockout doubles the duration (30 min, 1 h, 2 h, 4 h…). The lockout is cleared on a successful PIN reset.",
)
async def verify_pin(
    chat_id: ChatIdPath,
    payload: VerifyPinRequest,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[VerifyPinResponse]:
    result = await service.verify_pin(chat_id, payload)
    return ApiResponse(
        message=result["message"],
        data=VerifyPinResponse(success=result["success"], message=result["message"]),
    )


@auth_router.post(
    "/{chat_id}/disable",
    response_model=ApiResponse[UserResponse],
    summary="Disable account",
    description="Soft-disable the account. While disabled all actions are blocked except re-enabling via POST /auth/users/enable.",
)
async def disable_account(
    chat_id: ChatIdPath,
    service: UserService = Depends(_get_user_service),
) -> ApiResponse[UserResponse]:
    user = await service.disable_account(chat_id)
    return ApiResponse(
        message="Account disabled successfully", data=UserResponse.model_validate(user)
    )


@auth_router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete account",
    description="Mark the account as deleted.",
)
async def soft_delete_account(
    chat_id: ChatIdPath,
    service: UserService = Depends(_get_user_service),
) -> None:
    await service.soft_delete(chat_id)
