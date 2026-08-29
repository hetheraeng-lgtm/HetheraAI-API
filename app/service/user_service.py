from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user import User
from app.repository.user_repository import UserRepository
from app.schema.user import (
    EnableAccountRequest,
    ResetPinRequest,
    SetPinRequest,
    UserCreateRequest,
    UserUpdate,
    VerifyPinRequest,
)
from app.utils.security import hash_password, verify_password

_BASE_LOCKOUT_MINUTES = 15
_INITIAL_FAIL_THRESHOLD = 3


class UserService:

    def __init__(self, session: AsyncSession, repo: UserRepository) -> None:
        self.session = session
        self.repo = repo

    async def register(self, data: UserCreateRequest) -> tuple[User, bool]:
        user = await self.repo.get_by_chat_id(data.chat_id)

        if user:
            return user, False
        user = User(chat_id=data.chat_id, chat_type=data.chat_type.value)

        await self.repo.add(user)
        await self.session.commit()

        return user, True

    async def set_pin(self, chat_id: str, data: SetPinRequest) -> User:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        self._require_active(user)

        if user.transaction_pin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A transaction PIN is already set. Use the reset PIN endpoint to change it.",
            )

        user.transaction_pin = hash_password(data.pin)
        user.pin_failed_attempts = 0
        user.pin_lockout_count = 0
        user.pin_locked_until = None
        await self.session.commit()

        return user

    async def verify_pin(self, chat_id: str, data: VerifyPinRequest) -> dict:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        self._require_active(user)

        if not user.transaction_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No transaction PIN has been set",
            )

        now = datetime.now(timezone.utc)

        if user.pin_locked_until and user.pin_locked_until > now:
            remaining_seconds = (user.pin_locked_until - now).total_seconds()
            remaining_minutes = int(remaining_seconds / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {remaining_minutes} minute(s).",
            )

        if verify_password(data.pin, user.transaction_pin):
            user.pin_failed_attempts = 0
            user.pin_lockout_count = 0
            user.pin_locked_until = None
            await self.session.commit()
            return {"success": True, "message": "PIN verified successfully"}

        user.pin_failed_attempts += 1
        # After the first lockout event each individual wrong attempt triggers a new lockout
        threshold = _INITIAL_FAIL_THRESHOLD if user.pin_lockout_count == 0 else 1

        if user.pin_failed_attempts >= threshold:
            duration = self._lockout_duration_minutes(user.pin_lockout_count)
            user.pin_locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=duration
            )
            user.pin_lockout_count += 1
            user.pin_failed_attempts = 0
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Account locked for {duration} minute(s).",
            )

        remaining = threshold - user.pin_failed_attempts
        await self.session.commit()

        return {
            "success": False,
            "message": f"Incorrect PIN. {remaining} attempt(s) remaining before lockout.",
        }

    async def reset_pin(self, chat_id: str, data: ResetPinRequest) -> User:
        """Reset PIN even while PIN-locked; still blocked if account is disabled."""
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        self._require_active(user)

        if not user.transaction_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No transaction PIN has been set",
            )

        if not verify_password(data.old_pin, user.transaction_pin):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Old PIN is incorrect"
            )

        if data.old_pin == data.new_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New PIN must be different from the old PIN",
            )

        user.transaction_pin = hash_password(data.new_pin)
        user.pin_failed_attempts = 0
        user.pin_lockout_count = 0
        user.pin_locked_until = None
        await self.session.commit()

        return user

    async def disable_account(self, chat_id: str) -> User:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        self._require_active(user)
        user.is_active = False
        await self.session.commit()

        return user

    async def enable_account(self, data: EnableAccountRequest) -> User:
        user = await self.repo.get_by_chat_id(data.chat_id)

        if not user or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is not disabled",
            )

        if not user.transaction_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No transaction PIN has been set",
            )

        if not verify_password(data.pin, user.transaction_pin):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN"
            )

        user.is_active = True
        await self.session.commit()

        return user

    async def soft_delete(self, chat_id: str) -> User:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        self._require_not_deleted(user)
        user.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()

        return user

    async def get_by_chat_id(self, chat_id: str) -> User | None:
        return await self.repo.get_by_chat_id(chat_id)

    async def list_users(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.repo.get_all(skip=skip, limit=limit)

    async def update_user(self, chat_id: str, data: UserUpdate) -> User | None:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if not update_data:
            return user

        await self.repo.update(user, update_data)
        await self.session.commit()

        return user

    async def delete_user(self, chat_id: str) -> bool:
        user = await self.repo.get_by_chat_id(chat_id)

        if not user:
            return False

        await self.repo.delete(user)
        await self.session.commit()

        return True

    def _require_not_deleted(self, user: User) -> None:
        if user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

    def _require_active(self, user: User) -> None:
        self._require_not_deleted(user)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Re-enable your account to continue.",
            )

    def _lockout_duration_minutes(self, lockout_count: int) -> int:
        return _BASE_LOCKOUT_MINUTES * (2**lockout_count)
