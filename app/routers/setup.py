"""
首次安装向导 API
"""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.admin import SetupAdminPayload, SetupModelPayload, SetupWeComPayload
from app.services.runtime_config_service import runtime_config_service
from app.services.setup_service import setup_service
from app.services.tunnel_service import tunnel_service


router = APIRouter(prefix="/setup", tags=["安装向导"])


def _require_setup_write_access(request: Request) -> None:
    if runtime_config_service.is_setup_complete() and not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Admin authentication required")


def _validate_model_payload(payload: SetupModelPayload) -> None:
    provider = payload.model_provider.strip().lower() or "glm"
    if provider not in {"glm", "openai", "openai_compatible"}:
        raise HTTPException(status_code=400, detail="不支持的模型供应商")

    if provider == "glm":
        if not payload.zhipu_api_key.strip():
            raise HTTPException(status_code=400, detail="GLM 模式下必须填写 API Key")
        if not payload.zhipu_model.strip():
            raise HTTPException(status_code=400, detail="GLM 模式下必须填写模型名称")
        return

    if not payload.openai_api_key.strip():
        raise HTTPException(status_code=400, detail="OpenAI-compatible 模式下必须填写 API Key")
    if not payload.openai_base_url.strip():
        raise HTTPException(status_code=400, detail="OpenAI-compatible 模式下必须填写 Base URL")

    mode = payload.openai_model_mode.strip().lower() or "manual"
    if mode not in {"manual", "auto"}:
        raise HTTPException(status_code=400, detail="不支持的模型模式")

    if mode == "manual":
        if not payload.openai_model.strip():
            raise HTTPException(status_code=400, detail="手动模式下必须填写模型名称")
        return

    if not payload.openai_models.chat_model.strip():
        raise HTTPException(status_code=400, detail="Auto 模式下必须填写聊天模型")
    if not payload.openai_models.memory_model.strip():
        raise HTTPException(status_code=400, detail="Auto 模式下必须填写记忆模型")
    if not payload.openai_models.proactive_model.strip():
        raise HTTPException(status_code=400, detail="Auto 模式下必须填写主动消息模型")


@router.get("/status")
async def get_setup_status():
    return setup_service.get_status()


@router.put("/config/model")
async def save_setup_model(payload: SetupModelPayload, request: Request):
    _require_setup_write_access(request)
    _validate_model_payload(payload)
    runtime_config_service.save_section(
        "model",
        {
            "model_provider": payload.model_provider.strip(),
            "zhipu_api_key": payload.zhipu_api_key.strip(),
            "zhipu_model": payload.zhipu_model.strip(),
            "zhipu_thinking_type": payload.zhipu_thinking_type.strip(),
            "openai_api_key": payload.openai_api_key.strip(),
            "openai_base_url": payload.openai_base_url.strip().rstrip("/"),
            "openai_model_mode": payload.openai_model_mode.strip(),
            "openai_model": payload.openai_model.strip(),
            "openai_models": {
                "chat_model": payload.openai_models.chat_model.strip(),
                "memory_model": payload.openai_models.memory_model.strip(),
                "proactive_model": payload.openai_models.proactive_model.strip(),
            },
        },
    )
    return setup_service.get_status()


@router.put("/config/wecom")
async def save_setup_wecom(payload: SetupWeComPayload, request: Request):
    _require_setup_write_access(request)
    runtime_config_service.save_section(
        "wecom",
        {
            "corp_id": payload.corp_id.strip(),
            "agent_id": payload.agent_id.strip(),
            "secret": payload.secret.strip(),
            "token": payload.token.strip(),
            "encoding_aes_key": payload.encoding_aes_key.strip(),
        },
    )
    if payload.public_base_url.strip():
        runtime_config_service.save_section(
            "deployment",
            {"public_base_url": payload.public_base_url.strip().rstrip("/")},
        )
    return setup_service.get_status()


@router.put("/config/admin")
async def save_setup_admin(payload: SetupAdminPayload, request: Request):
    _require_setup_write_access(request)
    password = payload.password.strip()
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="管理员密码至少 6 位")
    runtime_config_service.save_section("admin", {"password": password})
    return setup_service.get_status()


@router.post("/validate")
async def validate_setup(request: Request):
    _require_setup_write_access(request)
    return await setup_service.validate()


@router.post("/tunnel/restart")
async def restart_tunnel(request: Request):
    _require_setup_write_access(request)
    return tunnel_service.restart()
