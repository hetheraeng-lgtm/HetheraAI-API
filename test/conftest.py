"""Shared test fixtures.

`test_transactions.py` is written against an older wallet-balance transaction
model (`app.model.wallet.Wallet`) that no longer exists anywhere in `app/model`
— see CLAUDE.md, which flags it as stale/aspirational rather than a spec of
current behavior. It's excluded from collection here rather than rewritten,
since reconciling it is a separate, larger task than the admin auth/dashboard
work these fixtures support.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config.database import get_db
from app.model.base import Base

collect_ignore = ["test_transactions.py"]


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_session):
    fastapi_app = create_app()

    async def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_payload():
    return {
        "username": "admin",
        "email": "admin@hethera.ai",
        "password": "SuperSecret123",
    }
