import hashlib
import hmac
import json
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import run_agent
from app.config import app_settings
from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.chat import ChatRequest, ChatResponse
from app.schema.common import ApiResponse, ChatIdPath

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chatbot"])


@router.get(
    "/whatsapp-webhook",
    summary="Verify the WhatsApp webhook",
    description=(
        "Meta's webhook verification handshake. Called once when the webhook "
        "URL is registered (and whenever Meta re-verifies it) — not part of "
        "normal message delivery."
    ),
)
async def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> PlainTextResponse:
    if (
        hub_mode == "subscribe"
        and hub_verify_token == app_settings.WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(hub_challenge)

    _log.warning("WhatsApp webhook verification failed (mode=%s)", hub_mode)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed"
    )


def _verify_whatsapp_signature(body: bytes, signature_header: str) -> bool:
    """Verify Meta's HMAC-SHA256 signature over the raw webhook request body.

    Meta signs every webhook payload with the app's App Secret and sends it
    as `X-Hub-Signature-256: sha256=<hex digest>`. Without this check, anyone
    who finds the webhook URL could POST fabricated messages and have them
    run through the agent (and, since write tools are enabled, potentially
    trigger real purchases) as if they came from a real WhatsApp user.

    No bypass for local/DEBUG testing, unlike the Paystack webhook elsewhere
    in this app — verify the payload, always, no exceptions. If
    WHATSAPP_APP_SECRET isn't configured, every request is rejected rather
    than accepted unverified (fail closed, not open).
    """
    if not app_settings.WHATSAPP_APP_SECRET:
        _log.error("WHATSAPP_APP_SECRET is not configured — rejecting webhook request")
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    expected = hmac.new(
        app_settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header[len(prefix) :])


@router.post(
    "/whatsapp-webhook",
    status_code=status.HTTP_200_OK,
    summary="Receive WhatsApp messages",
    description=(
        "WhatsApp webhook endpoint. Verifies Meta's request signature, parses "
        "incoming text messages, runs them through the chatbot agent, and "
        "sends the reply back over WhatsApp."
    ),
)
async def whatsapp_chat_with_bot(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
    session: AsyncSession = Depends(get_db),
) -> dict:
    body = await request.body()

    if not _verify_whatsapp_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
        )

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        )

    # Always ack with 200 from here on, regardless of what happens below — a
    # non-2xx response makes Meta retry delivery of this same webhook call,
    # which would mean re-running (and re-replying to) the same message.
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                try:
                    await _handle_whatsapp_message(message, session)
                except Exception:
                    _log.exception("Failed to handle WhatsApp message: %s", message)

    return {"status": "ok"}


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


async def _handle_whatsapp_message(message: dict, session: AsyncSession) -> None:
    chat_id = message.get("from")
    if not chat_id:
        _log.warning("WhatsApp message missing 'from': %s", message)
        return

    if message.get("type") != "text":
        _log.info(
            "Ignoring non-text WhatsApp message type=%s from=%s",
            message.get("type"),
            chat_id,
        )
        return

    text = (message.get("text") or {}).get("body")
    if not text:
        _log.warning("WhatsApp text message missing body: %s", message)
        return

    user = await UserRepository(session).get_by_chat_id(chat_id)
    if not user:
        await _send_whatsapp_message(
            chat_id,
            "You're not registered on Hethera yet. Please sign up first before chatting.",
        )
        return

    reply = await run_agent(chat_id=chat_id, message=text)
    await _send_whatsapp_message(chat_id, reply)


async def _send_whatsapp_message(to: str, text: str) -> None:
    if (
        not app_settings.WHATSAPP_ACCESS_TOKEN
        or not app_settings.WHATSAPP_PHONE_NUMBER_ID
    ):
        _log.warning(
            "WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID not configured — "
            "cannot send WhatsApp reply to %s",
            to,
        )
        return

    url = (
        f"https://graph.facebook.com/{app_settings.WHATSAPP_API_VERSION}/"
        f"{app_settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {app_settings.WHATSAPP_ACCESS_TOKEN}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            _log.exception("Failed to send WhatsApp message to %s", to)
