from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import run_agent
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.chat import ChatRequest, ChatResponse
from app.schema.common import ApiResponse, ChatIdPath

router = APIRouter(prefix="/chat", tags=["Chatbot"])


@router.post(
    "/{chat_id}",
    response_model=ApiResponse[ChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Chat with the bill-payment assistant",
    description=(
        "Send a natural-language message to the LangGraph ReAct agent. The agent "
        "decides which FastMCP bill-payment tools (if any) it needs, calls them, "
        "and returns a final response grounded in their results."
    ),
)
async def chat_with_bot(
    chat_id: ChatIdPath,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatResponse]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    reply = await run_agent(chat_id=chat_id, message=payload.message)

    return ApiResponse(message="Response from chatbot", data=ChatResponse(reply=reply))
