import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class SuperAdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class SuperAdminUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None


class SuperAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
