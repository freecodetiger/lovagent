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


@router.get("/status")
async def get_setup_status():
    return setup_service.get_status()


@router.put("/config/model")
async def save_setup_model(payload: SetupModelPayload, request: Request):
    _require_setup_write_access(request)
    runtime_config_service.save_section("model", payload.model_dump())
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
