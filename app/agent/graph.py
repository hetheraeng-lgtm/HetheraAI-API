"""LangGraph ReAct agent for the bill-payment chatbot.

Flow: Chat Request -> agent node (Reason) -> tools node (FastMCP tool call +
Observe) -> agent node (Reason again) -> ... -> Final Response, exactly the
loop described in FEATURE.md. Adding a bill-payment capability later is just
registering another FastMCP tool (app/mcp_server/tools/) — this graph's two
nodes and their edges never need to change.
"""

from collections.abc import Sequence
from typing import Any, cast

from fastmcp import Client
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.mcp_tools import build_langchain_tools
from app.config import app_settings
from app.mcp_server import mcp as fastmcp_server

_SYSTEM_PROMPT = SystemMessage(
    content=(
        "You are Hethera's bill-payment assistant. You help users with airtime, "
        "mobile data, cable TV and electricity questions.\n\n"
        "You have no built-in knowledge of providers, plans, prices or availability — "
        "that information only ever comes from calling your tools. Never guess or "
        "invent a plan, price, or provider that a tool didn't return.\n\n"
        "For an affordability or recommendation question (e.g. 'what MTN plan can I "
        "get with ₦200?'), find the right provider's tool, fetch its available plans, "
        "then reason over the returned options yourself: filter to ones at or under the "
        "stated budget, and note that different durations (daily/weekly/monthly) may "
        "fit different budgets. Present a short, concise list of the plans that fit, "
        "each with its price, and let the user decide based on how long they want it "
        "to last. If nothing fits the budget, say so plainly instead of stretching the "
        "budget or substituting a costlier plan.\n\n"
        "If a request needs a capability you don't have a tool for yet, say what you "
        "can't do rather than guessing."
    )
)


def _build_graph(tools: Sequence[BaseTool]) -> CompiledStateGraph:
    # ChatAnthropic's synthesized pydantic __init__ only exposes its fields'
    # validation aliases (model_name/api_key/max_tokens_to_sample/...) to the
    # type checker, even though populate_by_name=True lets the plain field
    # names (model/anthropic_api_key/max_tokens) used below through at
    # runtime — cast to Any to construct by field name without Pylance
    # flagging every one of them as an unknown parameter.
    anthropic_model_cls = cast(Any, ChatAnthropic)
    model = anthropic_model_cls(
        model=app_settings.AGENT_MODEL,
        anthropic_api_key=app_settings.ANTHROPIC_API_KEY,
        max_tokens=4096,
    ).bind_tools(tools)

    async def call_model(state: MessagesState) -> dict[str, list[BaseMessage]]:
        response = await model.ainvoke([_SYSTEM_PROMPT, *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def _extract_text(content: str | list[str | dict[Any, Any]]) -> str:
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


async def run_agent(chat_id: str, message: str) -> str:
    """Run one chat turn through the ReAct agent and return its final reply.

    Single-turn for now (no persisted history) — the request only needs a
    chat_id + message today so per-user conversational memory can be layered
    in later (e.g. a LangGraph checkpointer keyed by chat_id) without
    changing this function's signature or the API contract.
    """
    async with Client(fastmcp_server) as mcp_client:
        tools = await build_langchain_tools(mcp_client, chat_id)
        graph = _build_graph(tools)
        result: dict[str, Any] = await graph.ainvoke(
            {"messages": [HumanMessage(content=message)]}
        )

    messages: list[BaseMessage] = result["messages"]
    return _extract_text(messages[-1].content)
