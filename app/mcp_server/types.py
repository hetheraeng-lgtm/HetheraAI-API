import uuid
from typing import Annotated

from pydantic import BeforeValidator, Field

ChatId = Annotated[
    str,
    Field(
        description="Chat ID that uniquely identifies the acting user.",
        examples=["08119995541"],
    ),
]


def _coerce_uuid(v: object) -> object:
    """Accept a UUID string for a uuid.UUID tool parameter.

    JSON has no UUID type, so an MCP caller can only ever send a UUID as a
    plain string. FastMCP's strict input validation (app/mcp_server/server.py)
    rejects a string for a uuid.UUID-typed parameter outright — it requires an
    actual UUID instance, even for a bare function parameter (not just a
    BaseModel field). A `mode="before"` validator runs ahead of that check
    regardless of strict mode, so converting here is the reliable fix — the
    same situation, and the same fix, as the Decimal amounts in
    app/schema/transaction.py.
    """
    if isinstance(v, str):
        try:
            return uuid.UUID(v)
        except ValueError:
            pass
    return v


UUIDParam = Annotated[uuid.UUID, BeforeValidator(_coerce_uuid)]
