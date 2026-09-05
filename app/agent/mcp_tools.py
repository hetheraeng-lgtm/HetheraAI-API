"""Bridges FastMCP tools (app/mcp_server) into LangChain tools for the chat agent.

FastMCP stays the single source of truth for bill-payment products, prices and
availability — this module only translates already-registered MCP tool schemas
into the shape LangGraph's tool-calling loop expects. It never re-describes or
duplicates bill-payment data or service logic itself.

`langchain-mcp-adapters` would normally do this translation, but it is pinned
to the mcp<2 wire format while fastmcp>=4.0.2 requires mcp>=2.0 for its
in-process client, so the two can't be installed together. The adapter below
covers only what this project needs from that library.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import Client
from fastmcp.client.client import CallToolResult
from langchain_core.tools import StructuredTool
from mcp import types as mcp_types

# Tool names following this project's MCP naming convention (see
# app/mcp_server/tools/*.py) that only read data — no money moves, no writes.
# The chat agent is limited to these until purchase flows get an explicit
# confirmation step; exposing a new read-only tool to the agent needs no
# change here, and lifting this restriction for a write tool is a one-line
# addition to this tuple, not a redesign.
_READ_ONLY_PREFIXES = ("list_", "get_")


def _is_read_only(tool: mcp_types.Tool) -> bool:
    return tool.name.startswith(_READ_ONLY_PREFIXES)


def _text_content(result: CallToolResult) -> str:
    return "\n".join(
        block.text for block in result.content if isinstance(block, mcp_types.TextContent)
    )


def _format_result(result: CallToolResult) -> str:
    if result.is_error:
        return f"Error: {_text_content(result) or 'The tool call failed.'}"

    # `.data` is FastMCP's already-unwrapped Python value for the tool's
    # return (e.g. a plain list, not VTpass's raw `{"result": [...]}`
    # envelope) — fall back to the raw text content for void-returning tools.
    if result.data is not None:
        payload: Any = result.data
        return payload if isinstance(payload, str) else json.dumps(payload, default=str)

    return _text_content(result) or "Done."


def _build_call(
    client: Client, tool_name: str, chat_id: str, injects_chat_id: bool
) -> Callable[..., Awaitable[str]]:
    async def _call(**kwargs: Any) -> str:
        arguments = dict(kwargs)
        if injects_chat_id:
            arguments["chat_id"] = chat_id
        result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        return _format_result(result)

    return _call


def _to_langchain_tool(client: Client, tool: mcp_types.Tool, chat_id: str) -> StructuredTool:
    schema: dict[str, Any] = dict(tool.input_schema)
    properties: dict[str, Any] = dict(schema.get("properties", {}))
    injects_chat_id = "chat_id" in properties

    if injects_chat_id:
        # Never let the model supply the acting user's identity — it's bound
        # server-side from the authenticated chat session instead.
        properties = {k: v for k, v in properties.items() if k != "chat_id"}
        schema = {
            **schema,
            "properties": properties,
            "required": [r for r in schema.get("required", []) if r != "chat_id"],
        }

    return StructuredTool(
        name=tool.name,
        description=tool.description or tool.name,
        args_schema=schema,
        coroutine=_build_call(client, tool.name, chat_id, injects_chat_id),
    )


async def build_langchain_tools(client: Client, chat_id: str) -> list[StructuredTool]:
    """List the connected FastMCP server's read-only tools as LangChain tools."""
    tools = await client.list_tools()
    return [_to_langchain_tool(client, tool, chat_id) for tool in tools if _is_read_only(tool)]
