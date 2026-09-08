from app.mcp_server.db import session_scope
from app.mcp_server.errors import translate_errors
from app.mcp_server.server import mcp
from app.mcp_server.types import ChatId, UUIDParam
from app.mcp_server.users import resolve_user
from app.schema.transaction import (
    BeneficiaryCreateRequest,
    BeneficiaryResponse,
    BeneficiaryUpdateRequest,
)
from app.service.beneficiary_service import BeneficiaryService


@mcp.tool
async def list_beneficiaries(
    chat_id: ChatId, service_type: str | None = None
) -> list[BeneficiaryResponse]:
    """List a user's saved beneficiaries, optionally filtered by service_type."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = BeneficiaryService(session)
        items = await service.list_beneficiaries(user.id, service_type)
        return [BeneficiaryResponse.model_validate(b) for b in items]


@mcp.tool
async def add_beneficiary(
    chat_id: ChatId, payload: BeneficiaryCreateRequest
) -> BeneficiaryResponse:
    """Save a new beneficiary for quick future purchases."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = BeneficiaryService(session)
        async with translate_errors():
            b = await service.add_beneficiary(
                user_id=user.id,
                name=payload.name,
                identifier=payload.identifier,
                service_type=payload.service_type,
                service_id=payload.service_id,
            )
        return BeneficiaryResponse.model_validate(b)


@mcp.tool
async def update_beneficiary(
    chat_id: ChatId, beneficiary_id: UUIDParam, payload: BeneficiaryUpdateRequest
) -> BeneficiaryResponse:
    """Update the name, identifier, or service_id of a saved beneficiary."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = BeneficiaryService(session)
        async with translate_errors():
            b = await service.update_beneficiary(
                user_id=user.id,
                beneficiary_id=beneficiary_id,
                name=payload.name,
                identifier=payload.identifier,
                service_id=payload.service_id,
            )
        return BeneficiaryResponse.model_validate(b)


@mcp.tool
async def delete_beneficiary(chat_id: ChatId, beneficiary_id: UUIDParam) -> None:
    """Soft-delete a saved beneficiary."""
    async with session_scope() as session:
        user = await resolve_user(session, chat_id)
        service = BeneficiaryService(session)
        async with translate_errors():
            await service.delete_beneficiary(user.id, beneficiary_id)
