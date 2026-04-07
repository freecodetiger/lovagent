"""
Shared generation subgraphs.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Dict, List

from langgraph.graph import END, START, StateGraph

from app.graph.state import (
    IncomingGraphState,
    PreviewGraphState,
    ProactiveChatGraphState,
    append_graph_trace,
    append_tool_trace,
)
from app.graph.tools import web_search_tool
from app.prompts.templates import build_dynamic_prompt, build_proactive_prompt
from app.services.llm_service import glm_service
from app.services.proactive_chat_service import proactive_chat_service
from app.utils.helpers import (
    choose_natural_fallback_reply,
    get_current_time,
    is_response_too_similar,
)


ANTI_REPEAT_RETRY_INSTRUCTION = """

# Retry Rule
- 你刚刚生成的回复和最近几轮表达太像了。
- 这次必须换一个开头、换一个安慰或回应角度、换一个收尾。
- 不要重复“我在呢”“抱抱”“我也想你”这类刚用过的原句，除非用户明确要求。
- 保持同样的人设和情绪，但写得更像这一次临场接话。
"""


async def _chat_with_retry(
    *,
    system_prompt: str,
    user_message: str,
    context_messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    try:
        return await glm_service.chat_with_context(
            system_prompt=system_prompt,
            user_message=user_message,
            context_messages=context_messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        print(f"图执行生成失败，尝试轻量重试: {exc}")
        try:
            return await glm_service.chat_with_context(
                system_prompt=system_prompt,
                user_message=user_message,
                context_messages=[],
                temperature=max(0.1, temperature - 0.04),
                top_p=max(0.1, top_p - 0.03),
                max_tokens=max_tokens,
            )
        except Exception as retry_exc:
            print(f"图执行轻量重试失败: {retry_exc}")
            return ""


async def _incoming_collect_web_context(state: IncomingGraphState) -> IncomingGraphState:
    web_search_context = await web_search_tool.ainvoke({"user_message": state["user_content"]})
    return {
        "web_search_context": web_search_context,
        "graph_trace": append_graph_trace(state, "generation.incoming.collect_web_context"),
        "tool_trace": append_tool_trace(state, "web_search_tool"),
    }


async def _incoming_build_prompt(state: IncomingGraphState) -> IncomingGraphState:
    system_prompt = build_dynamic_prompt(
        user_input=state["user_content"],
        user_emotion=state["user_emotion"],
        agent_emotion=state["agent_emotion"],
        context=state["context"],
        current_time=get_current_time(),
        recent_agent_replies=state["recent_agent_replies"],
        persona_config=state["persona_config"],
        user_profile=state["user_memory"],
        web_search_context=state["web_search_context"],
    )
    return {
        "system_prompt": system_prompt,
        "graph_trace": append_graph_trace(state, "generation.incoming.build_prompt"),
    }


async def _incoming_generate_reply(state: IncomingGraphState) -> IncomingGraphState:
    reply = await _chat_with_retry(
        system_prompt=state["system_prompt"],
        user_message=state["user_content"],
        context_messages=state["context_messages"],
        max_tokens=int(state["response_constraints"]["max_tokens"]),
        temperature=0.88,
        top_p=0.93,
    )
    return {
        "agent_response": reply,
        "graph_trace": append_graph_trace(state, "generation.incoming.generate_reply"),
    }


def _incoming_retry_needed(state: IncomingGraphState) -> str:
    if state["agent_response"] and is_response_too_similar(state["agent_response"], state["recent_agent_replies"]):
        return "retry"
    return "finalize"


async def _incoming_retry_similar(state: IncomingGraphState) -> IncomingGraphState:
    retry_prompt = f"{state['system_prompt']}{ANTI_REPEAT_RETRY_INSTRUCTION}"
    regenerated = ""
    try:
        regenerated = await glm_service.chat_with_context(
            system_prompt=retry_prompt,
            user_message=state["user_content"],
            context_messages=state["context_messages"],
            temperature=0.95,
            top_p=0.95,
            max_tokens=int(state["response_constraints"]["max_tokens"]),
        )
    except Exception as exc:
        print(f"图执行重复抑制重试失败: {exc}")

    return {
        "agent_response": regenerated or state["agent_response"],
        "graph_trace": append_graph_trace(state, "generation.incoming.retry_similar"),
    }


async def _incoming_finalize_reply(state: IncomingGraphState) -> IncomingGraphState:
    return {
        "agent_response": state["agent_response"] or choose_natural_fallback_reply(
            state["user_content"],
            state["user_emotion"],
        ),
        "graph_trace": append_graph_trace(state, "generation.incoming.finalize_reply"),
    }


async def _preview_collect_web_context(state: PreviewGraphState) -> PreviewGraphState:
    web_search_context = await web_search_tool.ainvoke({"user_message": state["user_message"]})
    return {
        "web_search_context": web_search_context,
        "graph_trace": append_graph_trace(state, "generation.preview.collect_web_context"),
        "tool_trace": append_tool_trace(state, "web_search_tool"),
    }


async def _preview_build_prompt(state: PreviewGraphState) -> PreviewGraphState:
    prompt = build_dynamic_prompt(
        user_input=state["user_message"],
        user_emotion=state["user_emotion"],
        agent_emotion=state["agent_emotion"],
        context=state["context"],
        current_time=get_current_time(),
        recent_agent_replies=state["recent_agent_replies"],
        persona_config=state["persona_config"],
        user_profile=state["user_memory"],
        web_search_context=state["web_search_context"],
    )
    return {
        "prompt": prompt,
        "graph_trace": append_graph_trace(state, "generation.preview.build_prompt"),
    }


def _preview_mode_edge(state: PreviewGraphState) -> str:
    return state["preview_mode"]


async def _preview_generate_reply(state: PreviewGraphState) -> PreviewGraphState:
    reply = await _chat_with_retry(
        system_prompt=state["prompt"],
        user_message=state["user_message"],
        context_messages=state["context_messages"],
        max_tokens=int(state["response_constraints"]["max_tokens"]),
        temperature=0.88,
        top_p=0.93,
    )
    return {
        "reply": reply,
        "graph_trace": append_graph_trace(state, "generation.preview.generate_reply"),
    }


async def _preview_finalize_reply(state: PreviewGraphState) -> PreviewGraphState:
    if state["preview_mode"] == "prompt":
        return {
            "graph_trace": append_graph_trace(state, "generation.preview.finalize_reply"),
        }

    return {
        "reply": state["reply"] or choose_natural_fallback_reply(state["user_message"], state["user_emotion"]),
        "graph_trace": append_graph_trace(state, "generation.preview.finalize_reply"),
    }


async def _proactive_build_prompt(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    prompt = build_proactive_prompt(
        trigger_type=state["trigger_type"],
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        persona_config=state["persona_config"],
        user_profile=state["user_memory"],
        context=state["context"],
        recent_agent_replies=state["recent_agent_replies"],
        tone_hint=state["proactive_config"]["tone_hint"],
    )
    return {
        "prompt": prompt,
        "graph_trace": append_graph_trace(state, "generation.proactive.build_prompt"),
    }


async def _proactive_generate_reply(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    reply = ""
    try:
        reply = await glm_service.chat_with_context(
            system_prompt=state["prompt"],
            user_message="请直接输出一条现在要主动发给他的微信消息。",
            context_messages=[],
            temperature=0.92,
            top_p=0.95,
            max_tokens=int(state["response_constraints"]["max_tokens"]),
            task_type="proactive",
        )
    except Exception as exc:
        print(f"生成主动聊天文案失败，使用兜底: {exc}")

    return {
        "reply": reply,
        "graph_trace": append_graph_trace(state, "generation.proactive.generate_reply"),
    }


async def _proactive_finalize_reply(state: ProactiveChatGraphState) -> ProactiveChatGraphState:
    return {
        "reply": state["reply"] or proactive_chat_service._build_fallback_message(
            state["target_channel"],
            state["target_external_user_id"],
            state["trigger_type"],
            state["user_memory"],
        ),
        "graph_trace": append_graph_trace(state, "generation.proactive.finalize_reply"),
    }


@lru_cache(maxsize=1)
def get_incoming_generation_subgraph():
    graph = StateGraph(IncomingGraphState)
    graph.add_node("collect_web_context", _incoming_collect_web_context)
    graph.add_node("build_prompt", _incoming_build_prompt)
    graph.add_node("generate_reply", _incoming_generate_reply)
    graph.add_node("retry_similar", _incoming_retry_similar)
    graph.add_node("finalize_reply", _incoming_finalize_reply)
    graph.add_edge(START, "collect_web_context")
    graph.add_edge("collect_web_context", "build_prompt")
    graph.add_edge("build_prompt", "generate_reply")
    graph.add_conditional_edges(
        "generate_reply",
        _incoming_retry_needed,
        {"retry": "retry_similar", "finalize": "finalize_reply"},
    )
    graph.add_edge("retry_similar", "finalize_reply")
    graph.add_edge("finalize_reply", END)
    return graph.compile(name="incoming_generation_subgraph")


@lru_cache(maxsize=1)
def get_preview_generation_subgraph():
    graph = StateGraph(PreviewGraphState)
    graph.add_node("collect_web_context", _preview_collect_web_context)
    graph.add_node("build_prompt", _preview_build_prompt)
    graph.add_node("generate_reply", _preview_generate_reply)
    graph.add_node("finalize_reply", _preview_finalize_reply)
    graph.add_edge(START, "collect_web_context")
    graph.add_edge("collect_web_context", "build_prompt")
    graph.add_conditional_edges(
        "build_prompt",
        _preview_mode_edge,
        {"prompt": "finalize_reply", "reply": "generate_reply"},
    )
    graph.add_edge("generate_reply", "finalize_reply")
    graph.add_edge("finalize_reply", END)
    return graph.compile(name="preview_generation_subgraph")


@lru_cache(maxsize=1)
def get_proactive_generation_subgraph():
    graph = StateGraph(ProactiveChatGraphState)
    graph.add_node("build_prompt", _proactive_build_prompt)
    graph.add_node("generate_reply", _proactive_generate_reply)
    graph.add_node("finalize_reply", _proactive_finalize_reply)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "generate_reply")
    graph.add_edge("generate_reply", "finalize_reply")
    graph.add_edge("finalize_reply", END)
    return graph.compile(name="proactive_generation_subgraph")
