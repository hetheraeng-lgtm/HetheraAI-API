from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """DB session for MCP tools, which run outside FastAPI's request/Depends lifecycle."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
