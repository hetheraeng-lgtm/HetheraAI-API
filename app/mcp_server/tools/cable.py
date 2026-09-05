from typing import Annotated

from pydantic import Field

from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.providers import get_paystack, get_vtpass
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId
from app.mcp_server.users import resolve_user
from app.schema.transaction import (
    CablePurchaseRequest,
    TransactionResponse,
    VerifySmartcardRequest,
)
from app.service.cable_service import CableService
from app.utils.libs.vtpass.interfaces import VtpassVerifyResponse

ServiceId = Annotated[
    str, Field(description="Cable TV provider ID.", examples=["gotv"])
]


@mcp.tool
async def list_cable_providers() -> list[str]:
    """List supported cable TV provider IDs (e.g. 'gotv', 'dstv')."""
    async with session_scope() as session:
        return CableService(session, get_vtpass()).providers()


@mcp.tool
async def get_cable_variation_codes(service_id: ServiceId) -> dict:
    """Fetch available subscription package variation codes for a cable provider."""
    async with session_scope() as session:
        service = CableService(session, get_vtpass())
        async with translate_errors():
            return await service.get_variation_codes(service_id)


@mcp.tool
async def verify_cable_smartcard(
    payload: VerifySmartcardRequest,
) -> VtpassVerifyResponse | None:
    """Validate a cable TV smartcard number before purchase."""
    async with session_scope() as session:
        service = CableService(session, get_vtpass())
        async with translate_errors():
            return await service.verify_smartcard(
                payload.service_id, payload.smartcard_number
            )


@mcp.tool
async def buy_cable_subscription(
    chat_id: ChatId, payload: CablePurchaseRequest
) -> TransactionResponse:
    """Subscribe to a cable TV package using the user's saved card."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = CableService(session, get_vtpass())
        async with translate_errors():
            txn = await service.purchase(
                user_id=user.id,
                chat_id=chat_id,
                service_id=payload.service_id,
                smartcard_number=payload.smartcard_number,
                variation_code=payload.variation_code,
                idempotency_key=payload.idempotency_key,
                paystack=get_paystack(),
            )
        return TransactionResponse.model_validate(txn)
