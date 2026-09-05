from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import HTTPException
from fastmcp.exceptions import ToolError

from app.exceptions import AppException


@asynccontextmanager
async def translate_errors() -> AsyncGenerator[None, None]:
    """Map service-layer exceptions to client-facing tool errors instead of raw stack traces."""
    try:
        yield
    except HTTPException as exc:
        raise ToolError(str(exc.detail)) from exc
    except AppException as exc:
        raise ToolError(exc.message) from exc
