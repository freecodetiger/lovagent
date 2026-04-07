"""
Incoming message graph assembly.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.executors import save_conversation, schedule_memory_processing
from app.graph.state import IncomingGraphState, append_graph_trace, append_tool_trace, build_incoming_initial_state
from app.graph.subgraphs import get_incoming_context_loading_subgraph, get_incoming_generation_subgraph
from app.graph.tools import message_delivery_tool


async def _save_conversation_node(state: IncomingGraphState) -> IncomingGraphState:
    conversation_id = await save_conversation(
        user_id=state["user_id"],
        user_message=state["user_content"],
        agent_message=state["agent_response"],
        user_emotion=state["user_emotion"],
        agent_emotion=state["agent_emotion"],
    )
    return {
        "conversation_id": conversation_id,
        "graph_trace": append_graph_trace(state, "incoming.save_conversation"),
    }


async def _schedule_memory_node(state: IncomingGraphState) -> IncomingGraphState:
    schedule_memory_processing(
        wecom_user_id=state["user_id"],
        conversation_id=state["conversation_id"],
        user_message=state["user_content"],
        agent_message=state["agent_response"],
        user_emotion=state["user_emotion"],
        agent_emotion=state["agent_emotion"],
    )
    return {
        "graph_trace": append_graph_trace(state, "incoming.schedule_memory"),
    }


async def _deliver_reply_node(state: IncomingGraphState) -> IncomingGraphState:
    delivery_result = await message_delivery_tool.ainvoke(
        {
            "delivery_kind": "incoming_reply",
            "to_user": state["user_id"],
            "content": state["agent_response"],
        }
    )
    return {
        "delivery_result": delivery_result,
        "graph_trace": append_graph_trace(state, "incoming.deliver_reply"),
        "tool_trace": append_tool_trace(state, "message_delivery_tool"),
    }


@lru_cache(maxsize=1)
def get_incoming_message_graph():
    graph = StateGraph(IncomingGraphState)
    graph.add_node("context_loading_subgraph", get_incoming_context_loading_subgraph())
    graph.add_node("generation_subgraph", get_incoming_generation_subgraph())
    graph.add_node("save_conversation", _save_conversation_node)
    graph.add_node("schedule_memory", _schedule_memory_node)
    graph.add_node("deliver_reply", _deliver_reply_node)
    graph.add_edge(START, "context_loading_subgraph")
    graph.add_edge("context_loading_subgraph", "generation_subgraph")
    graph.add_edge("generation_subgraph", "save_conversation")
    graph.add_edge("save_conversation", "schedule_memory")
    graph.add_edge("schedule_memory", "deliver_reply")
    graph.add_edge("deliver_reply", END)
    return graph.compile(name="incoming_message_graph")


async def run_incoming_message_graph(payload: dict) -> IncomingGraphState:
    return await get_incoming_message_graph().ainvoke(build_incoming_initial_state(payload))
