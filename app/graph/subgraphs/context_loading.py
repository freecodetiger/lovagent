"""
Shared context-loading subgraphs.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.state import (
    IncomingGraphState,
    PreviewGraphState,
    ProactiveChatGraphState,
    append_graph_trace,
)
from app.services.emotion_engine import emotion_engine
from app.services.llm_service import glm_service
from app.services.memory_service import memory_service
from app.services.persona_service import persona_service
from app.services.proactive_chat_service import proactive_chat_service
from app.utils.helpers import get_response_constraints


async def _incoming_load_context(state: IncomingGraphState) -> IncomingGraphState:
    await memory_service.get_or_create_user(state["channel"], state["external_user_id"])
    persona_config = persona_service.get_persona_config()
    response_constraints = get_response_constraints(state["user_content"], persona_config.get("response_preferences"))
    context = await memory_service.get_conversation_context(state["channel"], state["external_user_id"])
    user_memory = await memory_service.get_user_memory(state["channel"], state["external_user_id"], query_text=state["user_content"])
    recent_agent_replies = await memory_service.get_recent_agent_replies(state["channel"], state["external_user_id"], limit=3)
    context_messages = await memory_service.get_recent_messages(
        state["channel"],
        state["external_user_id"],
        limit=int(response_constraints["context_limit"]),
    )
    return {
        "persona_config": persona_config,
        "response_constraints": response_constraints,
        "context": context,
        "user_memory": user_memory,
        "recent_agent_replies": recent_agent_replies,
        "context_messages": context_messages,
        "graph_trace": append_graph_trace(state, "context_loading.incoming.load_context"),
    }


async def _incoming_analyze_emotion(state: IncomingGraphState) -> IncomingGraphState:
    try:
        user_emotion = await glm_service.analyze_emotion(state["user_content"])
    except Exception as exc:
        print(f"图执行情绪分析失败，回退到默认情绪: {exc}")
        user_emotion = {"neutral": 1.0}

    agent_emotion = await emotion_engine.update_state(
        memory_service.build_user_key(state["channel"], state["external_user_id"]),
        state["user_content"],
        user_emotion,
    )
    return {
        "user_emotion": user_emotion,
        "agent_emotion": agent_emotion,
        "graph_trace": append_graph_trace(state, "context_loading.incoming.analyze_emotion"),
    }


async def _preview_load_context(state: PreviewGraphState) -> PreviewGraphState:
    channel = str(state.get("channel") or "").strip()
    external_user_id = str(state.get("external_user_id") or "").strip()
    user_memory = None
    context = {}
    recent_agent_replies = []
    context_messages = []

    if channel and external_user_id:
        user_memory = await memory_service.get_user_memory(channel, external_user_id, query_text=state["user_message"])
        if user_memory:
            context = await memory_service.get_conversation_context(channel, external_user_id)
            recent_agent_replies = await memory_service.get_recent_agent_replies(channel, external_user_id, limit=3)
            context_messages = await memory_service.get_recent_messages(channel, external_user_id, limit=4)

    persona_config = state["draft_config"] or persona_service.get_persona_config()
    response_constraints = get_response_constraints(state["user_message"], persona_config.get("response_preferences"))

    return {
        "persona_config": persona_config,
        "user_memory": user_memory,
        "context": context,
        "recent_agent_replies": recent_agent_replies,
        "context_messages": context_messages,
        "response_constraints": response_constraints,
        "graph_trace": append_graph_trace(state, "context_loading.preview.load_context"),
    }


async def _preview_analyze_emotion(state: PreviewGraphState) -> PreviewGraphState:
    user_emotion = await glm_service.analyze_emotion(state["user_message"])
    channel = str(state.get("channel") or "").strip()
    external_user_id = str(state.get("external_user_id") or "").strip()
    agent_emotion = await emotion_engine.update_state(
        memory_service.build_user_key(channel or "__preview__", external_user_id or "__preview__"),
        state["user_message"],
        user_emotion,
    )
    return {
        "user_emotion": user_emotion,
        "agent_emotion": agent_emotion,
        "graph_trace": append_graph_trace(state, "context_loading.preview.analyze_emotion"),
    }


async def _proactive_load_context(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    persona_config = persona_service.get_persona_config()
    proactive_config = proactive_chat_service.get_config()
    user_memory = await memory_service.get_user_memory(state["target_channel"], state["target_external_user_id"])
    context = await memory_service.get_conversation_context(state["target_channel"], state["target_external_user_id"])
    recent_agent_replies = await memory_service.get_recent_agent_replies(
        state["target_channel"],
        state["target_external_user_id"],
        limit=3,
    )
    response_constraints = get_response_constraints(
        "我想主动开启一段自然微信聊天",
        persona_config.get("response_preferences"),
    )
    return {
        "persona_config": persona_config,
        "proactive_config": proactive_config,
        "user_memory": user_memory,
        "context": context,
        "recent_agent_replies": recent_agent_replies,
        "response_constraints": response_constraints,
        "graph_trace": append_graph_trace(state, "context_loading.proactive.load_context"),
    }


@lru_cache(maxsize=1)
def get_incoming_context_loading_subgraph():
    graph = StateGraph(IncomingGraphState)
    graph.add_node("load_context", _incoming_load_context)
    graph.add_node("analyze_emotion", _incoming_analyze_emotion)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "analyze_emotion")
    graph.add_edge("analyze_emotion", END)
    return graph.compile(name="incoming_context_loading_subgraph")


@lru_cache(maxsize=1)
def get_preview_context_loading_subgraph():
    graph = StateGraph(PreviewGraphState)
    graph.add_node("load_context", _preview_load_context)
    graph.add_node("analyze_emotion", _preview_analyze_emotion)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "analyze_emotion")
    graph.add_edge("analyze_emotion", END)
    return graph.compile(name="preview_context_loading_subgraph")


@lru_cache(maxsize=1)
def get_proactive_context_loading_subgraph():
    graph = StateGraph(ProactiveChatGraphState)
    graph.add_node("load_context", _proactive_load_context)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", END)
    return graph.compile(name="proactive_context_loading_subgraph")
