from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.providers import get_paystack, get_vtpass
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId
from app.mcp_server.users import resolve_user
from app.schema.transaction import AirtimePurchaseRequest, TransactionResponse
from app.service.airtime_service import AirtimeService


@mcp.tool
async def list_airtime_providers() -> list[str]:
    """List supported airtime provider IDs (e.g. 'mtn', 'glo')."""
    async with session_scope() as session:
        return AirtimeService(session, get_vtpass()).providers()


@mcp.tool
async def buy_airtime(
    chat_id: ChatId, payload: AirtimePurchaseRequest
) -> TransactionResponse:
    """Purchase airtime for a phone number using the user's saved card."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = AirtimeService(session, get_vtpass())
        async with translate_errors():
            txn = await service.purchase(
                user_id=user.id,
                service_id=payload.service_id,
                phone=payload.phone,
                amount=payload.amount,
                idempotency_key=payload.idempotency_key,
                paystack=get_paystack(),
            )
        return TransactionResponse.model_validate(txn)
