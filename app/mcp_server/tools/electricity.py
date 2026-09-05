from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.providers import get_paystack, get_vtpass
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId
from app.mcp_server.users import resolve_user
from app.schema.transaction import (
    ElectricityPurchaseRequest,
    TransactionResponse,
    VerifyMeterRequest,
)
from app.service.electricity_service import ElectricityService
from app.utils.libs.vtpass.interfaces import VtpassVerifyResponse


@mcp.tool
async def list_electricity_providers() -> dict[str, str]:
    """List supported electricity providers, mapping abbreviation to service ID."""
    async with session_scope() as session:
        return ElectricityService(session, get_vtpass()).providers()


@mcp.tool
async def verify_electricity_meter(
    payload: VerifyMeterRequest,
) -> VtpassVerifyResponse | None:
    """Validate an electricity meter number before purchase."""
    async with session_scope() as session:
        service = ElectricityService(session, get_vtpass())
        async with translate_errors():
            return await service.validate_meter(
                payload.service_id, payload.meter_number, payload.meter_type
            )


@mcp.tool
async def buy_electricity(
    chat_id: ChatId, payload: ElectricityPurchaseRequest
) -> TransactionResponse:
    """Purchase electricity units using the user's saved card."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = ElectricityService(session, get_vtpass())
        async with translate_errors():
            txn = await service.purchase(
                user_id=user.id,
                chat_id=user.chat_id,
                service_id=payload.service_id,
                meter_number=payload.meter_number,
                variation_code=payload.meter_type,
                amount=payload.amount,
                idempotency_key=payload.idempotency_key,
                paystack=get_paystack(),
            )
        return TransactionResponse.model_validate(txn)
