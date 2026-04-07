"""
管理后台 API
"""

from hmac import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.graph import run_preview_graph
from app.config import settings
from app.services.emotion_engine import emotion_engine  # 兼容测试 patch
from app.services.llm_service import glm_service  # 兼容测试 patch
from app.schemas.admin import (
    AgentPersonaPayload,
    LoginRequest,
    PreviewRequest,
    ProactiveChatActionRequest,
    ProactiveChatPayload,
    UserMemoryPayload,
)
from app.services.memory_service import memory_service
from app.services.persona_service import persona_service
from app.services.proactive_chat_service import proactive_chat_service
from app.services.runtime_config_service import runtime_config_service

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
    preview = await run_preview_graph(
        {
            "preview_mode": "prompt",
            "user_message": payload.user_message,
            "wecom_user_id": payload.wecom_user_id,
            "draft_config": payload.draft_config.model_dump() if payload.draft_config else None,
        }
    )
    return {
        "prompt": preview.get("prompt", ""),
        "persona_config": preview.get("persona_config"),
        "user_memory": preview.get("user_memory"),
        "context_messages": preview.get("context_messages", []),
        "graph_trace": preview.get("graph_trace", []),
        "web_search_context": preview.get("web_search_context"),
    }


@router.post("/persona/preview-reply")
async def preview_reply(payload: PreviewRequest, _: bool = Depends(require_admin)):
    preview = await run_preview_graph(
        {
            "preview_mode": "reply",
            "user_message": payload.user_message,
            "wecom_user_id": payload.wecom_user_id,
            "draft_config": payload.draft_config.model_dump() if payload.draft_config else None,
        }
    )

    return {
        "prompt": preview.get("prompt", ""),
        "reply": preview.get("reply", ""),
        "persona_config": preview.get("persona_config"),
        "user_memory": preview.get("user_memory"),
        "graph_trace": preview.get("graph_trace", []),
        "web_search_context": preview.get("web_search_context"),
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
