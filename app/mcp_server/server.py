from fastmcp import FastMCP
from fastmcp.server.http import StarletteWithLifespan

mcp = FastMCP(
    name="hethera-utilities",
    instructions=(
        "Tools for purchasing airtime, mobile data, cable TV subscriptions and "
        "electricity, and for managing a user's saved beneficiaries and payment "
        "card. Every write tool takes a chat_id identifying the acting user."
    ),
    # Hide internal exception details from clients; ToolError messages still pass through.
    mask_error_details=True,
    strict_input_validation=True,
)


def create_mcp_app() -> StarletteWithLifespan:
    """ASGI app for mounting under the main FastAPI app, e.g. via app.mount()."""
    return mcp.http_app(path="/mcp")
