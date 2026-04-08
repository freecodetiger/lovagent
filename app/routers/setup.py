"""
首次安装向导 API
"""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.admin import SetupAdminPayload, SetupModelPayload, SetupWeComPayload
from app.services.provider_catalog import get_provider_preset, infer_provider_id
from app.services.runtime_config_service import runtime_config_service
from app.services.setup_service import setup_service
from app.services.tunnel_service import tunnel_service


router = APIRouter(prefix="/setup", tags=["安装向导"])


def _require_setup_write_access(request: Request) -> None:
    if runtime_config_service.is_setup_complete() and not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Admin authentication required")


def _resolve_model_payload(payload: SetupModelPayload) -> tuple[str, str, str, str]:
    payload_dict = payload.model_dump()
    provider_id = infer_provider_id(payload_dict)
    preset = get_provider_preset(provider_id)

    provider_api_key = payload.provider_api_key.strip()
    if not provider_api_key:
        provider_api_key = (
            payload.zhipu_api_key.strip()
            if preset.provider_id == "zhipu"
            else payload.openai_api_key.strip()
        )

    provider_base_url = payload.provider_base_url.strip().rstrip("/")
    if not provider_base_url and preset.transport == "openai_compatible":
        provider_base_url = payload.openai_base_url.strip().rstrip("/")
    provider_base_url = provider_base_url or preset.default_base_url.rstrip("/")

    openai_model_mode = payload.openai_model_mode.strip().lower() or "auto"
    return provider_id, provider_api_key, provider_base_url, openai_model_mode


def _validate_model_payload(payload: SetupModelPayload) -> None:
    provider_id, provider_api_key, provider_base_url, openai_model_mode = _resolve_model_payload(payload)
    preset = get_provider_preset(provider_id)
    if provider_id != preset.provider_id:
        raise HTTPException(status_code=400, detail="不支持的模型供应商")

    if not provider_api_key:
        raise HTTPException(status_code=400, detail=f"{preset.label} 模式下必须填写 API Key")

    if not provider_base_url:
        raise HTTPException(status_code=400, detail=f"{preset.label} 模式下必须填写 Base URL")

    search_mode = payload.search_provider_mode.strip() or "tavily_primary_exa_fallback"
    if search_mode not in {"disabled", "tavily_primary_exa_fallback", "tavily", "exa"}:
        raise HTTPException(status_code=400, detail="不支持的搜索模式")

    if preset.transport == "openai_compatible" and openai_model_mode == "manual" and not payload.openai_model.strip():
        raise HTTPException(status_code=400, detail="手动模式下必须填写模型名称")


@router.get("/status")
async def get_setup_status():
    return setup_service.get_status()


@router.put("/config/model")
async def save_setup_model(payload: SetupModelPayload, request: Request):
    _require_setup_write_access(request)
    _validate_model_payload(payload)
    provider_id, provider_api_key, provider_base_url, openai_model_mode = _resolve_model_payload(payload)
    preset = get_provider_preset(provider_id)
    runtime_config_service.save_section(
        "model",
        {
            "provider_id": provider_id,
            "provider_api_key": provider_api_key,
            "provider_base_url": provider_base_url,
            "text_model_override": payload.openai_model.strip() if preset.transport == "openai_compatible" and openai_model_mode == "manual" else "",
            "multimodal_model_override": "",
            "document_model_override": "",
            "tavily_api_key": payload.tavily_api_key.strip(),
            "exa_api_key": payload.exa_api_key.strip(),
            "search_provider_mode": payload.search_provider_mode.strip() or "tavily_primary_exa_fallback",
            "model_provider": preset.transport,
            "zhipu_api_key": payload.zhipu_api_key.strip() or (provider_api_key if preset.provider_id == "zhipu" else ""),
            "zhipu_model": payload.zhipu_model.strip(),
            "zhipu_thinking_type": payload.zhipu_thinking_type.strip(),
            "multimodal_api_key": payload.multimodal_api_key.strip() or (provider_api_key if preset.supports_multimodal else ""),
            "multimodal_model": payload.multimodal_model.strip(),
            "openai_api_key": payload.openai_api_key.strip() or (provider_api_key if preset.transport == "openai_compatible" else ""),
            "openai_base_url": payload.openai_base_url.strip().rstrip("/") or provider_base_url,
            "openai_model_mode": openai_model_mode,
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
