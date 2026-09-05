import copy
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import app_settings
from app.config.middlewares import middlewares
from app.controller.admin.user_controller import router as admin_users_router
from app.controller.admin.admin_controller import admin_router
from app.controller.admin.admin_controller import (
    auth_router as admin_auth_router,
)
from app.controller.general.user_controller import auth_router as user_auth_router
from app.controller.general.chatbot_controller import router as chatbot_router
from app.controller.general.airtime_controller import router as airtime_router
from app.controller.general.mobile_data import router as mobile_data_router
from app.controller.general.cable_controller import router as cable_router
from app.controller.general.electricity_controller import router as electricity_router
from app.controller.general.card_controller import router as card_router
from app.controller.general.beneficiary_controller import router as beneficiary_router
from app.controller.general.vtpass_controller import router as vtpass_router
from app.controller.general.paystack_controller import router as paystack_router
from app.mcp_server import create_mcp_app

_USER_TAGS = {
    "User Authentication",
    "Chatbot",
    "Airtime",
    "Mobile Data",
    "Cable TV",
    "Electricity",
    "Cards",
    "Beneficiaries",
    "VTPass",
    "Paystack",
}
_ADMIN_TAGS = {
    "Super Admin Authentication",
    "Super Admin Management",
    "User Management",
}

# Navigation bar injected at the top of every Swagger UI page
_NAV = """
<div style="background:#1b1b1b;padding:6px 16px;display:flex;align-items:center;
            gap:10px;position:fixed;top:0;left:0;right:0;z-index:9999;
            font-family:sans-serif;font-size:13px">
  <span style="color:#aaa">Docs:</span>
  <a href="/docs"       style="color:#85ea2d;padding:3px 10px;background:#333;border-radius:4px;text-decoration:none">All</a>
  <a href="/docs/users" style="color:#85ea2d;padding:3px 10px;background:#333;border-radius:4px;text-decoration:none">Users</a>
  <a href="/docs/admin" style="color:#85ea2d;padding:3px 10px;background:#333;border-radius:4px;text-decoration:none">Admin</a>
</div>
<style>.swagger-ui .topbar { margin-top: 38px !important; }</style>
"""


def _filter_schema(schema: dict, tags: set[str]) -> dict:
    filtered = copy.deepcopy(schema)
    filtered["paths"] = {
        path: {
            m: op
            for m, op in methods.items()
            if not isinstance(op, dict) or bool(set(op.get("tags", [])) & tags)
        }
        for path, methods in schema.get("paths", {}).items()
        if any(
            isinstance(op, dict) and set(op.get("tags", [])) & tags
            for op in methods.values()
        )
    }
    filtered["tags"] = [t for t in schema.get("tags", []) if t.get("name") in tags]
    return filtered


def _swagger_page(openapi_url: str, title: str) -> HTMLResponse:
    html = bytes(
        get_swagger_ui_html(openapi_url=openapi_url, title=title).body
    ).decode()
    return HTMLResponse(html.replace("<body>", f"<body>{_NAV}", 1))


def create_app() -> FastAPI:
    # FastMCP's ASGI app owns its own startup/shutdown (session manager, etc.),
    # so FastAPI's lifespan must delegate to it for the mounted MCP routes to work.
    mcp_app = create_mcp_app()

    app = FastAPI(
        title=app_settings.APP_NAME.capitalize(),
        description=f"{app_settings.APP_NAME.capitalize()}'s API documentation",
        docs_url=None,
        openapi_url="/openapi.json",
        middleware=middlewares,
        lifespan=mcp_app.lifespan,
    )

    prefix = app_settings.API_VERSION
    app.include_router(user_auth_router, prefix=prefix)
    app.include_router(chatbot_router, prefix=prefix)
    app.include_router(admin_auth_router, prefix=prefix)
    app.include_router(admin_router, prefix=prefix)
    app.include_router(admin_users_router, prefix=prefix)
    app.include_router(airtime_router, prefix=prefix)
    app.include_router(mobile_data_router, prefix=prefix)
    app.include_router(cable_router, prefix=prefix)
    app.include_router(electricity_router, prefix=prefix)
    app.include_router(card_router, prefix=prefix)
    app.include_router(beneficiary_router, prefix=prefix)
    app.include_router(vtpass_router, prefix=prefix)
    app.include_router(paystack_router, prefix=prefix)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "failed", "message": exc.detail, "data": None},
            headers=getattr(exc, "headers", None) or {},
        )

    # ── filtered OpenAPI schemas ──────────────────────────────────────────────

    @app.get("/openapi/users.json", include_in_schema=False)
    async def openapi_users() -> JSONResponse:
        return JSONResponse(_filter_schema(app.openapi(), _USER_TAGS))

    @app.get("/openapi/admin.json", include_in_schema=False)
    async def openapi_admin() -> JSONResponse:
        return JSONResponse(_filter_schema(app.openapi(), _ADMIN_TAGS))

    # ── Swagger UI pages ──────────────────────────────────────────────────────

    @app.get("/")
    @app.get("")
    async def welcome_page() -> HTMLResponse:
        return HTMLResponse(
            "<h1>Welcome to Hethera Utilities API</h1><p>Use the /docs endpoint to explore the API documentation.</p>"
        )

    @app.get("/docs", include_in_schema=False)
    async def swagger_full() -> HTMLResponse:
        return _swagger_page("/openapi.json", f"{app_settings.APP_NAME} — Full")

    @app.get("/docs/users", include_in_schema=False)
    async def swagger_users() -> HTMLResponse:
        return _swagger_page("/openapi/users.json", f"{app_settings.APP_NAME} — Users")

    @app.get("/docs/admin", include_in_schema=False)
    async def swagger_admin() -> HTMLResponse:
        return _swagger_page("/openapi/admin.json", f"{app_settings.APP_NAME} — Admin")

    # Mounted last: only handles paths not matched by the routers/routes above (serves /mcp).
    app.mount("/", mcp_app)

    return app
