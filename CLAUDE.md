# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hethera is a FastAPI backend for a chat-driven bill-payment assistant (WhatsApp-style `chat_id` as the user identity, no traditional login for end users). Users buy airtime, mobile data, cable TV and electricity through VTpass, paying via a saved Paystack card. A super-admin side (JWT auth) manages users and VTpass config. An MCP server (via `fastmcp`) exposes the same purchase/beneficiary/card actions as tools for an LLM agent, mounted into the same ASGI app as the REST API.

## Commands

Dependencies are managed with `uv` (see `uv.lock`); the local `.venv` is a uv-managed venv.

```bash
uv sync                          # install/sync dependencies from uv.lock
uv run fastapi dev main.py       # run the API with reload (app = create_app())
uv run uvicorn main:app --reload # equivalent, direct uvicorn
python -m app.mcp_server         # run the MCP server standalone (stdio), see app/mcp_server/__main__.py
```

Database (Postgres via Docker, see `docker/db-compose.yaml`):

```bash
docker compose -f docker/db-compose.yaml up -d   # starts postgres on localhost:5445, data in .db-volume/
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

Note: `.env` holds real credentials for VTpass/Paystack/DB/Redis and is required — `AppSettings` (`app/config/__init__.py`) has no defaults for most of these and will raise on import if missing.

**Tests:** `pytest`/`pytest-asyncio` are used in `test/` but are not declared in `pyproject.toml` and are not installed in `.venv` — running `uv run pytest` will fail until they're added as a dependency group. Additionally, `test/conftest.py` and `test/test_transactions.py` are written against an older wallet-balance transaction model (`app.model.wallet.Wallet`, `wallet_repo.get_by_user_id_with_lock`, debit/credit of a stored balance) that no longer exists in `app/model` — the current `TransactionService` (see below) charges the user's saved Paystack card directly per purchase instead of debiting a wallet. Treat this test file as stale/aspirational, not a spec of current behavior, unless you're explicitly asked to reconcile it.

## Architecture

**Layering:** `controller` (FastAPI routers, HTTP concerns only) → `service` (business logic) → `repository` (`BaseRepository[ModelType]` in `app/repository/base.py`, thin SQLAlchemy query wrappers) → `model` (SQLAlchemy `Base`/`TimestampMixin` declarative models, `app/model/base.py`). Every layer takes an `AsyncSession` passed down from `app/config/database.py`'s `get_db()` dependency. Controllers build services with a small `_get_x_service(session = Depends(get_db))` factory function rather than a DI container.

**App assembly (`app/__init__.py`):** `create_app()` builds the FastMCP ASGI app first, then the FastAPI app delegates its `lifespan` to `mcp_app.lifespan` (required for FastMCP's mounted session manager to start/stop correctly), registers all REST routers under `app_settings.API_VERSION` (`/api/v1`), and finally `app.mount("/", mcp_app)` **last** so it only catches unmatched paths (serves `/mcp`). Routes are tagged `_USER_TAGS`/`_ADMIN_TAGS` and there are three separate Swagger UIs (`/docs`, `/docs/users`, `/docs/admin`) built by filtering the OpenAPI schema by tag — adding a new router means picking the right tag set or it won't show up in the split docs.

**Transaction/payment flow (the core domain logic, `app/service/transaction_service.py`):** `TransactionService.execute_purchase()` is the single entry point every utility service (`airtime_service.py`, `mobile_data_service.py`, `cable_service.py`, `electricity_service.py`) calls. Sequence: idempotency check (returns existing txn if `idempotency_key` seen) → load the user's one saved `UserCard` → record `Transaction` (status `INITIATED`) with paired ledger entries → transition to `PROCESSING` and commit *before* any external call → charge the card via Paystack → verify the charge settled → call the VTpass `provider_callable` → finalize to `SUCCESSFUL`/`FAILED`/`UNKNOWN` based on the result. If VTpass fails after the card was successfully charged, compensating ledger entries are created and a Paystack refund is issued (`_handle_vtpass_failure`). `TransactionStatus` transitions are only valid per `VALID_TRANSITIONS` in `app/enums/transaction.py`, enforced by `TransactionService._transition()` (raises `InvalidTransactionStateError` otherwise); every transition is also recorded via `TransactionAuditRepository`. `LedgerService` (`app/service/ledger_service.py`) maintains double-entry `LedgerAccount`/`LedgerEntry` records per user+currency and per provider-clearing account, and asserts debits == credits on every write (`_assert_balanced`).

**Error handling:** Domain errors are custom `AppException` subclasses (`app/exceptions.py`: `InsufficientBalanceError`, `InvalidTransactionStateError`, `WalletNotFoundError`, `DuplicateIdempotencyKeyError`, etc.) or plain FastAPI `HTTPException`. The global `http_exception_handler` in `app/__init__.py` wraps all `HTTPException`s into the standard `{"status": "failed", "message": ..., "data": null}` envelope — every REST response should conform to `ApiResponse[T]` (`app/schema/common.py`, `{status, message, data}`). MCP tools use a different translation path: `app/mcp_server/errors.py`'s `translate_errors()` context manager catches `HTTPException`/`AppException` and re-raises as `fastmcp.exceptions.ToolError` so raw stack traces never reach MCP clients (the server also sets `mask_error_details=True`).

**MCP server (`app/mcp_server/`):** A single module-level `FastMCP` instance (`server.py`) is imported by every file in `app/mcp_server/tools/` and decorated with `@mcp.tool`. Each tool follows the same shape: open a DB session via `session_scope()` (`db.py` — a standalone session because MCP tools run outside FastAPI's request/`Depends` lifecycle), resolve the acting `User` from the `chat_id` argument via `resolve_user()` (`users.py`, raises `ToolError` if unknown), instantiate the relevant `*Service`, run the mutation inside `async with translate_errors():`, and return a Pydantic response model. New tool modules must be imported in `app/mcp_server/tools/__init__.py` (import-only, `# noqa: F401`) or `@mcp.tool` never registers them. `ChatId` (`types.py`) is the shared annotated type for the identifying argument across every tool. `providers.py` builds fresh `VtpassService`/`PaystackService` instances per call from `app_settings` — there's no shared/cached client.

**Provider integrations (`app/utils/libs/`):** `vtpass/` and `paystack/` each follow `interfaces.py` (typed request/response dataclasses/pydantic models, e.g. `BuyAirtimeData`, `FlattenedVtpassResponse`, `PaystackOptions`, `PaystackMetadata`) + `service.py` (the HTTP client wrapper, constructed with an `Options` object carrying API keys/base URL from `app_settings`). Services are instantiated per-request/per-tool-call, not shared singletons.

**Models registration for Alembic:** `migrations/env.py` does `import app.model  # noqa: F401` to force every model module to register on `Base.metadata` before autogenerate diffs the schema — a new model file must be imported from `app/model/__init__.py` or Alembic won't see it.

**Admin vs. general split:** `app/controller/admin/` (JWT-protected via `get_current_super_admin` in `app/controller/admin/deps.py`, using `OAuth2PasswordBearer` + `app.utils.security.decode_access_token`) vs. `app/controller/general/` (end-user endpoints keyed by `chat_id`, no bearer auth — the chat platform is the trust boundary). Don't mix admin auth deps into general routers or vice versa.

**Timestamps:** All `TimestampMixin` timestamps default to `Africa/Lagos` (`WAT`) time in Python but the DB column `server_default` is `NOW()` (UTC) — this mismatch is intentional/pre-existing in `app/model/base.py` and `app/model/ledger.py`, not something to "fix" without checking with the team first.
