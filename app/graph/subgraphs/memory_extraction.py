"""
Shared memory extraction subgraph.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.executors.memory import load_memory_update_context
from app.graph.state import MemoryUpdateGraphState, append_graph_trace, append_tool_trace
from app.graph.tools import memory_extract_tool
from app.services.memory_service import memory_service


async def _prepare_context(state: MemoryUpdateGraphState) -> MemoryUpdateGraphState:
    existing_memory, recent_messages = await load_memory_update_context(state["wecom_user_id"])
    return {
        "existing_memory": existing_memory,
        "recent_messages": recent_messages,
        "graph_trace": append_graph_trace(state, "memory_extraction.prepare_context"),
    }


async def _rule_extract(state: MemoryUpdateGraphState) -> MemoryUpdateGraphState:
    return {
        "rule_result": memory_service._rule_extract_memory(state["user_message"], state["user_emotion"]),
        "graph_trace": append_graph_trace(state, "memory_extraction.rule_extract"),
    }


def _should_run_llm(state: MemoryUpdateGraphState) -> str:
    if memory_service._should_use_llm_memory_extraction(state["user_message"]):
        return "llm"
    return "merge"


async def _llm_extract(state: MemoryUpdateGraphState) -> MemoryUpdateGraphState:
    llm_result = await memory_extract_tool.ainvoke(
        {
            "user_message": state["user_message"],
            "agent_message": state["agent_message"],
            "existing_memory": state["existing_memory"],
            "short_term_memory": state["existing_memory"].get("short_term_memory"),
            "recent_messages": state["recent_messages"],
        }
    )
    return {
        "llm_result": llm_result,
        "graph_trace": append_graph_trace(state, "memory_extraction.llm_extract"),
        "tool_trace": append_tool_trace(state, "memory_extract_tool"),
    }


async def _merge_results(state: MemoryUpdateGraphState) -> MemoryUpdateGraphState:
    return {
        "extracted": memory_service._merge_extraction_results(
            state["rule_result"],
            state["llm_result"],
            user_emotion=state["user_emotion"],
        ),
        "graph_trace": append_graph_trace(state, "memory_extraction.merge_results"),
    }


@lru_cache(maxsize=1)
def get_memory_extraction_subgraph():
    graph = StateGraph(MemoryUpdateGraphState)
    graph.add_node("prepare_context", _prepare_context)
    graph.add_node("rule_extract", _rule_extract)
    graph.add_node("llm_extract", _llm_extract)
    graph.add_node("merge_results", _merge_results)
    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "rule_extract")
    graph.add_conditional_edges(
        "rule_extract",
        _should_run_llm,
        {"llm": "llm_extract", "merge": "merge_results"},
    )
    graph.add_edge("llm_extract", "merge_results")
    graph.add_edge("merge_results", END)
    return graph.compile(name="memory_extraction_subgraph")
