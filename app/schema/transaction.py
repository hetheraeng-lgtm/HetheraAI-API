import uuid
from app.schema.common import (
    ALL_PROVIDERS,
    AIRTIME_PROVIDERS,
    CABLE_PROVIDERS,
    ELECTRICITY_PROVIDERS,
    DATA_PROVIDERS,
)
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums.transaction import TransactionStatus, TransactionType
from app.schema.common import (
    AIRTIME_PROVIDERS,
    DATA_PROVIDERS,
    CABLE_PROVIDERS,
    ELECTRICITY_PROVIDERS,
)
from app.utils.phone import validate_nigerian_phone


def uuid_schema_extra(schema: dict) -> None:
    schema["examples"] = [str(uuid4())]
    schema["format"] = "uuid"


_IDEMPOTENCY = Field(
    default_factory=lambda: str(uuid4()),
    min_length=1,
    max_length=128,
    json_schema_extra=uuid_schema_extra,
)


def _coerce_decimal_amount(v: object) -> object:
    """Accept a plain JSON number/string for a Decimal amount field.

    JSON has no Decimal type, so any caller sending amount over JSON — the
    MCP tool-calling path included, which runs FastMCP's strict input
    validation (app/mcp_server/server.py) — can only ever send an int, float,
    or numeric string. Pydantic's strict mode rejects those outright for a
    Decimal field (it requires an actual Decimal instance), even with
    `Field(strict=False)` on the field itself; a `mode="before"` validator
    runs ahead of that check regardless of strict mode, so converting here is
    the reliable fix. Non-Decimal, non-numeric input is passed through
    unchanged so pydantic's own error message still reports it.
    """
    if isinstance(v, (int, float, str)) and not isinstance(v, bool):
        try:
            return Decimal(str(v))
        except InvalidOperation:
            pass
    return v


# ── Purchase request schemas ─────────────────────────────────────────────────


class AirtimePurchaseRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["glo"])
    phone: str = Field(..., examples=["08119995541", "08111111111"])
    amount: Decimal = Field(gt=49, decimal_places=2)
    idempotency_key: str = _IDEMPOTENCY

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: object) -> object:
        return _coerce_decimal_amount(v)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_nigerian_phone(v)

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in AIRTIME_PROVIDERS:
            raise ValueError(
                f"service_id must be one of: {', '.join(AIRTIME_PROVIDERS)}"
            )
        return v


class MobileDataPurchaseRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["glo-data"])
    phone: str = Field(..., examples=["08119995541", "08111111111"])
    variation_code: str = Field(min_length=1, max_length=50, examples=["glo100"])
    idempotency_key: str = _IDEMPOTENCY

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_nigerian_phone(v)

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in DATA_PROVIDERS:
            raise ValueError(f"service_id must be one of: {', '.join(DATA_PROVIDERS)}")
        return v


class CablePurchaseRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["gotv"])
    smartcard_number: str = Field(min_length=1, max_length=50, examples=["1212121212"])
    variation_code: str = Field(min_length=1, max_length=50, examples=["gotv-lite"])
    idempotency_key: str = _IDEMPOTENCY

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in CABLE_PROVIDERS:
            raise ValueError(f"service_id must be one of: {', '.join(CABLE_PROVIDERS)}")
        return v


class ElectricityPurchaseRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["eko-electric"])
    meter_number: str = Field(min_length=1, max_length=50, examples=["1111111111111"])
    meter_type: str = Field(pattern=r"^(prepaid|postpaid)$")
    amount: Decimal = Field(ge=500, decimal_places=2)
    idempotency_key: str = _IDEMPOTENCY

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: object) -> object:
        return _coerce_decimal_amount(v)

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ELECTRICITY_PROVIDERS:
            raise ValueError(
                f"service_id must be one of: {', '.join(ELECTRICITY_PROVIDERS)}"
            )
        return v


class VerifyMeterRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["eko-electric"])
    meter_number: str = Field(min_length=1, max_length=50, examples=["1111111111111"])
    meter_type: str = Field(
        pattern=r"^(prepaid|postpaid)$", examples=["prepaid", "postpaid"]
    )

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ELECTRICITY_PROVIDERS:
            raise ValueError(
                f"service_id must be one of: {', '.join(ELECTRICITY_PROVIDERS)}"
            )
        return v


class VerifySmartcardRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=50, examples=["gotv"])
    smartcard_number: str = Field(min_length=1, max_length=50, examples=["1212121212"])


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    user_id: uuid.UUID
    card_id: uuid.UUID | None
    type: TransactionType
    status: TransactionStatus
    amount: Decimal
    currency: str
    provider: str
    service_id: str
    provider_reference: str | None
    paystack_reference: str | None
    paystack_fee: Decimal | None
    vtpass_cost: Decimal | None
    profit_loss: Decimal | None
    failure_reason: str | None
    extra_data: dict | None
    created_at: datetime
    updated_at: datetime


# ── Card schemas ─────────────────────────────────────────────────────────────


class CardInitializeRequest(BaseModel):
    email: str = Field(
        min_length=5, max_length=255, examples=["abimbolaolayemiwhyte@gmail.com"]
    )
    callback_url: str | None = Field(..., examples=["https://hetheraengineering.com"])


class CardInitializeResponse(BaseModel):
    authorization_url: str | None
    access_code: str | None
    reference: str | None


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last4: str
    card_type: str
    bank: str
    email: str
    created_at: datetime


# ── Beneficiary schemas ──────────────────────────────────────────────────────


class BeneficiaryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Mom"])
    identifier: str = Field(min_length=1, max_length=100, examples=["08109955312"])
    service_type: str = Field(min_length=1, max_length=50, examples=["airtime"])
    service_id: str = Field(min_length=1, max_length=50, examples=["mtn"])

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALL_PROVIDERS:
            raise ValueError(f"service_id must be one of: {', '.join(ALL_PROVIDERS)}")
        return v


class BeneficiaryUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=100, examples=["Mommy"]
    )
    identifier: str | None = Field(
        default=None, min_length=1, max_length=100, examples=["08109955312"]
    )
    service_id: str | None = Field(
        default=None, min_length=1, max_length=50, examples=["mtn-data"]
    )

    @field_validator("service_id", mode="before")
    @classmethod
    def validate_service_id(cls, v: str) -> str:
        if v is None:
            return v
        v = v.lower().strip()
        if v not in ALL_PROVIDERS:
            raise ValueError(f"service_id must be one of: {', '.join(ALL_PROVIDERS)}")
        return v


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    identifier: str
    service_type: str
    service_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
