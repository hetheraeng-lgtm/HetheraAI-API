# Hethera AI Backend Codebase

## Admin dashboard: local setup

```bash
docker compose -f docker/db-compose.yaml up -d   # Postgres :5445, Redis :6380
uv sync
uv run alembic upgrade head
uv run fastapi dev main.py                       # serves http://localhost:8000
```

CORS already allows `http://localhost:3000` (the admin dashboard's dev server) by default —
see `ALLOWED_ORIGINS` in `.env`.

**Create the first (and only) admin account.** There can be exactly one admin; every
subsequent call to `/register` returns `409 Conflict`:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@hethera.ai", "password": "<choose-a-strong-password>"}'
```

Then sign in from the dashboard frontend (`hethera-admin-dashboard`), or directly:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@hethera.ai", "password": "<your-password>"}'
```

Admin-only endpoints live under `/api/v1/admin/*` and `/api/v1/auth/admin/*`; browse them at
`/docs/admin`. Run the test suite with `uv run pytest test/` (`test_transactions.py` is
intentionally excluded — see the note at the top of `test/conftest.py`).

## Helpful materials

- Langchain reference for [factMCP](https://reference.langchain.com/python/langchain-mcp-adapters)
- Tutorials to watch
  - [langchain](https://academy.langchain.com/courses/foundation-introduction-to-langchain-python)
  - [langgraph](https://academy.langchain.com/courses/foundation-introduction-to-langchain-python)
  - [deep research agent](https://academy.langchain.com/courses/deep-research-with-langgraph)
  - [ambient-agents](https://academy.langchain.com/courses/ambient-agents)
  - [generative-ai](https://www.deeplearning.ai/specializations/generative-ai-for-software-development)
