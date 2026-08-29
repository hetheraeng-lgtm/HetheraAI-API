import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums.chat_type import ChatType

# exactly 8 numeric digits, no spaces or symbols
_PIN = Field(pattern=r"^\d{8}$")


class UserVerifyRequest(BaseModel):
    chat_id: str = Field(
        min_length=1, max_length=64, pattern=r"^\S+$", examples=["08119995541"]
    )


class UserVerifyResponse(BaseModel):
    chat_id: str
    is_new: bool


class UserCreateRequest(BaseModel):
    chat_id: str = Field(
        min_length=1, max_length=128, pattern=r"^\S+$", examples=["08119995541"]
    )
    chat_type: ChatType = Field(default=ChatType.WHATSAPP)


class UserCreateResponse(BaseModel):
    identifier: uuid.UUID
    is_new: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: str
    chat_type: str
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    is_active: bool | None = Field(default=None)


class SetPinRequest(BaseModel):
    pin: str = _PIN


class ResetPinRequest(BaseModel):
    old_pin: str = _PIN
    new_pin: str = _PIN


class VerifyPinRequest(BaseModel):
    pin: str = _PIN


class VerifyPinResponse(BaseModel):
    success: bool
    message: str


class EnableAccountRequest(BaseModel):
    chat_id: str = Field(
        min_length=1, max_length=128, pattern=r"^\S+$", examples=["08119995541"]
    )
    pin: str = _PIN
