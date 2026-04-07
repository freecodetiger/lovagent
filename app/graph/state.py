"""
LangGraph 状态定义与初始化。
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict


ChatMessage = Dict[str, str]
JsonDict = Dict[str, object]


class IncomingGraphState(TypedDict):
    user_id: str
    user_content: str
    persona_config: Dict
    response_constraints: Dict
    user_emotion: Dict
    agent_emotion: Dict
    context: Dict
    user_memory: Optional[Dict]
    recent_agent_replies: List[str]
    context_messages: List[ChatMessage]
    web_search_context: JsonDict
    system_prompt: str
    agent_response: str
    conversation_id: Optional[int]
    delivery_result: JsonDict
    graph_trace: List[str]
    tool_trace: List[str]


class PreviewGraphState(TypedDict):
    preview_mode: Literal["prompt", "reply"]
    user_message: str
    wecom_user_id: Optional[str]
    draft_config: Optional[Dict]
    persona_config: Dict
    user_memory: Optional[Dict]
    context: Dict
    context_messages: List[ChatMessage]
    recent_agent_replies: List[str]
    user_emotion: Dict
    agent_emotion: Dict
    web_search_context: JsonDict
    response_constraints: Dict
    prompt: str
    reply: str
    graph_trace: List[str]
    tool_trace: List[str]


class ProactiveChatGraphState(TypedDict):
    target_wecom_user_id: str
    trigger_type: str
    window_key: Optional[str]
    send_delivery: bool
    persona_config: Dict
    proactive_config: Dict
    user_memory: Optional[Dict]
    context: Dict
    recent_agent_replies: List[str]
    response_constraints: Dict
    prompt: str
    reply: str
    delivery: JsonDict
    graph_trace: List[str]
    tool_trace: List[str]


class MemoryUpdateGraphState(TypedDict):
    wecom_user_id: str
    conversation_id: int
    user_message: str
    agent_message: str
    user_emotion: Dict
    agent_emotion: Dict
    existing_memory: Dict
    recent_messages: List[ChatMessage]
    rule_result: Dict[str, object]
    llm_result: Dict[str, object]
    extracted: Dict[str, object]
    graph_trace: List[str]
    tool_trace: List[str]


def append_graph_trace(state: Dict, name: str) -> List[str]:
    return [*state.get("graph_trace", []), name]


def append_tool_trace(state: Dict, name: str) -> List[str]:
    return [*state.get("tool_trace", []), name]


def build_incoming_initial_state(payload: Dict[str, object]) -> IncomingGraphState:
    return {
        "user_id": str(payload.get("user_id") or ""),
        "user_content": str(payload.get("user_content") or ""),
        "persona_config": {},
        "response_constraints": {},
        "user_emotion": {},
        "agent_emotion": {},
        "context": {},
        "user_memory": None,
        "recent_agent_replies": [],
        "context_messages": [],
        "web_search_context": {"enabled": False, "triggered": False, "query": "", "results": []},
        "system_prompt": "",
        "agent_response": "",
        "conversation_id": None,
        "delivery_result": {"attempted": False, "status": "pending"},
        "graph_trace": [],
        "tool_trace": [],
    }


def build_preview_initial_state(payload: Dict[str, object]) -> PreviewGraphState:
    return {
        "preview_mode": payload.get("preview_mode", "prompt"),  # type: ignore[typeddict-item]
        "user_message": str(payload.get("user_message") or ""),
        "wecom_user_id": str(payload.get("wecom_user_id") or "").strip() or None,
        "draft_config": payload.get("draft_config") if isinstance(payload.get("draft_config"), dict) else None,
        "persona_config": {},
        "user_memory": None,
        "context": {},
        "context_messages": [],
        "recent_agent_replies": [],
        "user_emotion": {},
        "agent_emotion": {},
        "web_search_context": {"enabled": False, "triggered": False, "query": "", "results": []},
        "response_constraints": {},
        "prompt": "",
        "reply": "",
        "graph_trace": [],
        "tool_trace": [],
    }


def build_proactive_initial_state(payload: Dict[str, object]) -> ProactiveChatGraphState:
    return {
        "target_wecom_user_id": str(payload.get("target_wecom_user_id") or ""),
        "trigger_type": str(payload.get("trigger_type") or ""),
        "window_key": str(payload.get("window_key") or "").strip() or None,
        "send_delivery": bool(payload.get("send_delivery")),
        "persona_config": {},
        "proactive_config": {},
        "user_memory": None,
        "context": {},
        "recent_agent_replies": [],
        "response_constraints": {},
        "prompt": "",
        "reply": "",
        "delivery": {"attempted": False, "status": "pending"},
        "graph_trace": [],
        "tool_trace": [],
    }


def build_memory_initial_state(payload: Dict[str, object]) -> MemoryUpdateGraphState:
    return {
        "wecom_user_id": str(payload.get("wecom_user_id") or ""),
        "conversation_id": int(payload.get("conversation_id") or 0),
        "user_message": str(payload.get("user_message") or ""),
        "agent_message": str(payload.get("agent_message") or ""),
        "user_emotion": payload.get("user_emotion") if isinstance(payload.get("user_emotion"), dict) else {},
        "agent_emotion": payload.get("agent_emotion") if isinstance(payload.get("agent_emotion"), dict) else {},
        "existing_memory": {},
        "recent_messages": [],
        "rule_result": {},
        "llm_result": {},
        "extracted": {},
        "graph_trace": [],
        "tool_trace": [],
    }
