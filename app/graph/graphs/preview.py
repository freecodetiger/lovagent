"""
Preview graph assembly.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.state import PreviewGraphState, build_preview_initial_state
from app.graph.subgraphs import get_preview_context_loading_subgraph, get_preview_generation_subgraph


@lru_cache(maxsize=1)
def get_preview_graph():
    graph = StateGraph(PreviewGraphState)
    graph.add_node("context_loading_subgraph", get_preview_context_loading_subgraph())
    graph.add_node("generation_subgraph", get_preview_generation_subgraph())
    graph.add_edge(START, "context_loading_subgraph")
    graph.add_edge("context_loading_subgraph", "generation_subgraph")
    graph.add_edge("generation_subgraph", END)
    return graph.compile(name="preview_graph")


async def run_preview_graph(payload: dict) -> PreviewGraphState:
    return await get_preview_graph().ainvoke(build_preview_initial_state(payload))
