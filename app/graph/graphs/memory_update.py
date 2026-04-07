"""
Memory update graph assembly.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.executors import persist_memory_update
from app.graph.state import MemoryUpdateGraphState, append_graph_trace, build_memory_initial_state
from app.graph.subgraphs import get_memory_extraction_subgraph


async def _persist_node(state: MemoryUpdateGraphState) -> MemoryUpdateGraphState:
    await persist_memory_update(
        wecom_user_id=state["wecom_user_id"],
        conversation_id=state["conversation_id"],
        user_message=state["user_message"],
        agent_message=state["agent_message"],
        user_emotion=state["user_emotion"],
        extracted=state["extracted"],
    )
    return {
        "graph_trace": append_graph_trace(state, "memory_update.persist"),
    }


@lru_cache(maxsize=1)
def get_memory_update_graph():
    graph = StateGraph(MemoryUpdateGraphState)
    graph.add_node("memory_extraction_subgraph", get_memory_extraction_subgraph())
    graph.add_node("persist", _persist_node)
    graph.add_edge(START, "memory_extraction_subgraph")
    graph.add_edge("memory_extraction_subgraph", "persist")
    graph.add_edge("persist", END)
    return graph.compile(name="memory_update_graph")


async def run_memory_update_graph(payload: dict) -> MemoryUpdateGraphState:
    return await get_memory_update_graph().ainvoke(build_memory_initial_state(payload))
