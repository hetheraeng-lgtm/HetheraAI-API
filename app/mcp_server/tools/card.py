from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.providers import get_paystack
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId
from app.mcp_server.users import resolve_user
from app.schema.transaction import (
    CardInitializeRequest,
    CardInitializeResponse,
    CardResponse,
)
from app.service.card_service import CardService


@mcp.tool
async def initialize_card(
    chat_id: ChatId, payload: CardInitializeRequest
) -> CardInitializeResponse:
    """Generate a Paystack authorization URL. The user visits it to save a card."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = CardService(session, get_paystack())
        async with translate_errors():
            result = await service.initialize_card_authorization(
                user_id=user.id,
                email=payload.email,
                callback_url=payload.callback_url,
            )
        return CardInitializeResponse(**result)


@mcp.tool
async def get_card(chat_id: ChatId) -> CardResponse | None:
    """Get the saved card for a user."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = CardService(session, get_paystack())
        card = await service.get_card(user.id)
        return CardResponse.model_validate(card) if card else None


@mcp.tool
async def delete_card(chat_id: ChatId) -> None:
    """Remove the saved card for a user."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = CardService(session, get_paystack())
        async with translate_errors():
            await service.delete_card(user.id)
