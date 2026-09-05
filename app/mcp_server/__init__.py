from app.mcp_server.server import create_mcp_app, mcp
from app.mcp_server import tools as _tools  # noqa: F401  registers all tools on import

__all__ = ["mcp", "create_mcp_app"]
