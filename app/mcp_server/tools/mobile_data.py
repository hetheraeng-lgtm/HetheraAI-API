from typing import Annotated

from pydantic import Field

from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.providers import get_paystack, get_vtpass
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId
from app.mcp_server.users import resolve_user
from app.schema.transaction import MobileDataPurchaseRequest, TransactionResponse
from app.service.mobile_data_service import MobileDataService

ServiceId = Annotated[
    str, Field(description="Mobile data provider ID.", examples=["glo-data"])
]


@mcp.tool
async def list_mobile_data_providers() -> list[str]:
    """List supported mobile data provider IDs (e.g. 'glo-data', 'mtn-data')."""
    async with session_scope() as session:
        return MobileDataService(session, get_vtpass()).providers()


@mcp.tool
async def get_mobile_data_variation_codes(service_id: ServiceId) -> dict:
    """Fetch available data bundle variation codes for a provider from VTpass."""
    async with session_scope() as session:
        service = MobileDataService(session, get_vtpass())
        async with translate_errors():
            return await service.get_variation_codes(service_id)


@mcp.tool
async def buy_mobile_data(
    chat_id: ChatId, payload: MobileDataPurchaseRequest
) -> TransactionResponse:
    """Purchase a mobile data bundle for a phone number using the user's saved card."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = MobileDataService(session, get_vtpass())
        async with translate_errors():
            txn = await service.purchase(
                user_id=user.id,
                service_id=payload.service_id,
                phone=payload.phone,
                variation_code=payload.variation_code,
                idempotency_key=payload.idempotency_key,
                paystack=get_paystack(),
            )
        return TransactionResponse.model_validate(txn)
