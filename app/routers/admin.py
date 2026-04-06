"""
管理后台 API
"""

from hmac import compare_digest
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.config import settings
from app.prompts.templates import build_dynamic_prompt
from app.schemas.admin import (
    AgentPersonaPayload,
    LoginRequest,
    PreviewRequest,
    ProactiveChatActionRequest,
    ProactiveChatPayload,
    UserMemoryPayload,
)
from app.services.emotion_engine import emotion_engine
from app.services.llm_service import glm_service
from app.services.memory_service import memory_service
from app.services.persona_service import persona_service
from app.services.proactive_chat_service import proactive_chat_service
from app.services.runtime_config_service import runtime_config_service
from app.utils.helpers import choose_natural_fallback_reply, get_current_time, get_response_constraints

router = APIRouter(prefix="/admin-api", tags=["管理后台"])


def require_admin(request: Request) -> bool:
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return True


@router.post("/auth/login")
async def admin_login(payload: LoginRequest, request: Request):
    if not compare_digest(payload.password, runtime_config_service.get_effective_admin_password()):
        raise HTTPException(status_code=401, detail="Invalid password")

    request.session["is_admin"] = True
    return {"authenticated": True}


@router.post("/auth/logout")
async def admin_logout(request: Request, response: Response, _: bool = Depends(require_admin)):
    request.session.clear()
    response.delete_cookie(settings.admin_cookie_name)
    return {"authenticated": False}


@router.get("/me")
async def get_current_admin(request: Request):
    return {"authenticated": bool(request.session.get("is_admin"))}


@router.get("/persona")
async def get_persona(_: bool = Depends(require_admin)):
    return persona_service.get_persona_config()


@router.put("/persona")
async def update_persona(payload: AgentPersonaPayload, _: bool = Depends(require_admin)):
    return persona_service.save_persona_config(payload.model_dump())


@router.get("/proactive-chat")
async def get_proactive_chat(_: bool = Depends(require_admin)):
    return proactive_chat_service.get_config()


@router.put("/proactive-chat")
async def update_proactive_chat(payload: ProactiveChatPayload, _: bool = Depends(require_admin)):
    return proactive_chat_service.save_config(payload.model_dump())


@router.post("/proactive-chat/preview")
async def preview_proactive_chat(payload: ProactiveChatActionRequest, _: bool = Depends(require_admin)):
    try:
        return await proactive_chat_service.preview_outreach(payload.wecom_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/proactive-chat/run-once")
async def run_proactive_chat(payload: ProactiveChatActionRequest, _: bool = Depends(require_admin)):
    try:
        return await proactive_chat_service.run_outreach_once(payload.wecom_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/persona/preview-prompt")
async def preview_prompt(payload: PreviewRequest, _: bool = Depends(require_admin)):
    preview = await build_preview_payload(payload)
    return {
        "prompt": preview["prompt"],
        "persona_config": preview["persona_config"],
        "user_memory": preview["user_memory"],
        "context_messages": preview["context_messages"],
    }


@router.post("/persona/preview-reply")
async def preview_reply(payload: PreviewRequest, _: bool = Depends(require_admin)):
    preview = await build_preview_payload(payload)
    response_constraints = get_response_constraints(
        payload.user_message,
        preview["persona_config"].get("response_preferences"),
    )
    agent_response = ""

    try:
        agent_response = await glm_service.chat_with_context(
            system_prompt=preview["prompt"],
            user_message=payload.user_message,
            context_messages=preview["context_messages"],
            temperature=0.88,
            top_p=0.93,
            max_tokens=int(response_constraints["max_tokens"]),
        )
    except Exception as exc:
        print(f"管理后台预览回复失败，使用兜底: {exc}")

    if not agent_response:
        agent_response = choose_natural_fallback_reply(payload.user_message, preview["user_emotion"])

    return {
        "prompt": preview["prompt"],
        "reply": agent_response,
        "persona_config": preview["persona_config"],
        "user_memory": preview["user_memory"],
    }


@router.get("/users")
async def list_users(
    query: str = Query("", description="按企业微信用户 ID 或昵称搜索"),
    limit: int = Query(20, ge=1, le=50),
    _: bool = Depends(require_admin),
):
    return {"items": await memory_service.list_users(query=query, limit=limit)}


@router.get("/users/{wecom_user_id}/memory")
async def get_user_memory(wecom_user_id: str, _: bool = Depends(require_admin)):
    payload = await memory_service.get_user_memory(wecom_user_id)
    if not payload:
        raise HTTPException(status_code=404, detail="User not found")
    return payload


@router.put("/users/{wecom_user_id}/memory")
async def update_user_memory(
    wecom_user_id: str,
    payload: UserMemoryPayload,
    _: bool = Depends(require_admin),
):
    return await memory_service.upsert_user_memory(wecom_user_id, payload.model_dump())


@router.get("/users/{wecom_user_id}/conversations")
async def get_user_conversations(
    wecom_user_id: str,
    limit: int = Query(8, ge=1, le=20),
    _: bool = Depends(require_admin),
):
    return {"items": await memory_service.get_recent_conversations(wecom_user_id, limit=limit)}


async def build_preview_payload(payload: PreviewRequest) -> Dict:
    user_memory = None
    context = {}
    recent_agent_replies = []
    context_messages = []

    if payload.wecom_user_id:
        user_memory = await memory_service.get_user_memory(payload.wecom_user_id)
        if user_memory:
            context = await memory_service.get_conversation_context(payload.wecom_user_id)
            recent_agent_replies = await memory_service.get_recent_agent_replies(payload.wecom_user_id, limit=3)
            context_messages = await memory_service.get_recent_messages(payload.wecom_user_id, limit=4)

    user_emotion = await glm_service.analyze_emotion(payload.user_message)
    agent_emotion = await emotion_engine.update_state(
        payload.wecom_user_id or "__preview__",
        payload.user_message,
        user_emotion,
    )

    draft_config = payload.draft_config.model_dump() if payload.draft_config else None
    persona_config = draft_config or persona_service.get_persona_config()
    web_search_context = await glm_service.maybe_collect_web_context(payload.user_message)

    prompt = build_dynamic_prompt(
        user_input=payload.user_message,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
        context=context,
        current_time=get_current_time(),
        recent_agent_replies=recent_agent_replies,
        persona_config=persona_config,
        user_profile=user_memory,
        web_search_context=web_search_context,
    )

    return {
        "prompt": prompt,
        "persona_config": persona_config,
        "user_memory": user_memory,
        "context_messages": context_messages,
        "user_emotion": user_emotion,
        "web_search_context": web_search_context,
    }
