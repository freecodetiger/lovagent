"""
Proactive chat graph assembly.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.state import (
    ProactiveChatGraphState,
    append_graph_trace,
    append_tool_trace,
    build_proactive_initial_state,
)
from app.graph.subgraphs import get_proactive_context_loading_subgraph, get_proactive_generation_subgraph
from app.graph.tools import message_delivery_tool


def _delivery_edge(state: ProactiveChatGraphState) -> str:
    return "deliver" if state["send_delivery"] else "preview"


async def _deliver_node(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    delivery = await message_delivery_tool.ainvoke(
        {
            "delivery_kind": "proactive_outreach",
            "channel": state["target_channel"],
            "external_user_id": state["target_external_user_id"],
            "content": state["reply"],
            "trigger_type": state["trigger_type"],
            "window_key": state["window_key"],
        }
    )
    return {
        "delivery": delivery,
        "graph_trace": append_graph_trace(state, "proactive.deliver"),
        "tool_trace": append_tool_trace(state, "message_delivery_tool"),
    }


async def _preview_delivery_node(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    return {
        "delivery": {"attempted": False, "status": "preview"},
        "graph_trace": append_graph_trace(state, "proactive.preview_delivery"),
    }


@lru_cache(maxsize=1)
def get_proactive_chat_graph():
    graph = StateGraph(ProactiveChatGraphState)
    graph.add_node("context_loading_subgraph", get_proactive_context_loading_subgraph())
    graph.add_node("generation_subgraph", get_proactive_generation_subgraph())
    graph.add_node("deliver", _deliver_node)
    graph.add_node("preview_delivery", _preview_delivery_node)
    graph.add_edge(START, "context_loading_subgraph")
    graph.add_edge("context_loading_subgraph", "generation_subgraph")
    graph.add_conditional_edges(
        "generation_subgraph",
        _delivery_edge,
        {"deliver": "deliver", "preview": "preview_delivery"},
    )
    graph.add_edge("deliver", END)
    graph.add_edge("preview_delivery", END)
    return graph.compile(name="proactive_chat_graph")


async def run_proactive_chat_graph(payload: dict) -> ProactiveChatGraphState:
    return await get_proactive_chat_graph().ainvoke(build_proactive_initial_state(payload))
