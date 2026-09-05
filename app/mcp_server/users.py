from sqlalchemy.ext.asyncio import AsyncSession

from fastmcp.exceptions import ToolError

from app.model.user import User
from app.repository.user_repository import UserRepository


async def resolve_user(session: AsyncSession, chat_id: str) -> User:
    """Look up the acting user for a tool call. Raises ToolError if chat_id is unknown."""
    user = await UserRepository(session).get_by_chat_id(chat_id)
    if not user:
        raise ToolError(f"No user found for chat_id '{chat_id}'.")
    return user
