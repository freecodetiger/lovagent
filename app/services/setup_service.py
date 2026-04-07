"""
首次安装向导服务
"""

from typing import Dict

import httpx

from app.config import settings
from app.services.llm_service import glm_service
from app.services.runtime_config_service import runtime_config_service
from app.services.tunnel_service import (
    is_invalid_autodetected_tunnel_url,
    is_quick_tunnel_url,
    tunnel_service,
)
from app.services.wecom_service import wecom_service


class SetupService:
    """聚合初始化状态与校验逻辑。"""

    def _resolve_public_base_url(self, tunnel_status: Dict) -> str:
        configured_public_base_url = runtime_config_service.get_effective_public_base_url().strip().rstrip("/")
        tunnel_public_url = str(tunnel_status.get("public_url") or "").strip().rstrip("/")

        if tunnel_public_url and (
            not configured_public_base_url
            or is_quick_tunnel_url(configured_public_base_url)
            or is_invalid_autodetected_tunnel_url(configured_public_base_url)
        ):
            return tunnel_public_url

        return configured_public_base_url

    def _build_callback_url(self, public_base_url: str) -> str:
        if public_base_url:
            return f"{public_base_url.rstrip('/')}/wecom/callback"
        return f"http://{settings.server_host}:{settings.server_port}/wecom/callback"

    def get_status(self) -> Dict:
        status = runtime_config_service.get_status_payload()
        if (
            not status["current"]["public_base_url"]
            or is_quick_tunnel_url(status["current"]["public_base_url"])
            or is_invalid_autodetected_tunnel_url(status["current"]["public_base_url"])
        ):
            tunnel_service.ensure_started()

        tunnel_status = tunnel_service.get_status()
        resolved_public_base_url = self._resolve_public_base_url(tunnel_status)
        status["tunnel"] = tunnel_status
        status["current"]["public_base_url"] = resolved_public_base_url
        status["current"]["callback_url"] = self._build_callback_url(resolved_public_base_url)
        status["sections"]["deployment_configured"] = bool(resolved_public_base_url)
        status["setup_completed"] = all(status["sections"].values())
        return status

    async def validate(self) -> Dict:
        status = self.get_status()
        public_base_url = status["current"]["public_base_url"]
        checks = {
            "local_health": await self._check_local_health(),
            "public_health": await self._check_public_health(public_base_url),
            "model": await self._check_model(),
            "wecom": self._check_wecom(),
        }
        checks["callback"] = {
            "ok": bool(public_base_url),
            "detail": self._build_callback_url(public_base_url),
        }

        return {
            "all_passed": all(item["ok"] for item in checks.values()),
            "checks": checks,
            "status": status,
        }

    async def _check_local_health(self) -> Dict:
        url = f"http://127.0.0.1:{settings.server_port}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
            return {"ok": True, "detail": url}
        except Exception as exc:
            return {"ok": False, "detail": f"{url} -> {exc}"}

    async def _check_public_health(self, public_base_url: str) -> Dict:
        if not public_base_url:
            return {"ok": False, "detail": "未获取到公网 HTTPS 地址"}

        url = f"{public_base_url.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
            return {"ok": True, "detail": url}
        except Exception as exc:
            return {"ok": False, "detail": f"{url} -> {exc}"}

    async def _check_model(self) -> Dict:
        model_config = runtime_config_service.get_effective_model_config()
        provider = str(model_config.get("model_provider") or "glm").strip().lower()
        if not runtime_config_service.is_model_configured():
            if provider in {"openai", "openai_compatible"}:
                return {"ok": False, "detail": "未配置完整的 OpenAI-compatible 模型参数"}
            return {"ok": False, "detail": "未配置完整的 GLM 模型参数"}

        try:
            result = await glm_service.chat_completion(
                [{"role": "user", "content": "你好，请只回复“ok”"}],
                temperature=0.1,
                top_p=0.9,
                max_tokens=24,
            )
            detail_prefix = "OpenAI-compatible" if provider in {"openai", "openai_compatible"} else "GLM"
            return {"ok": bool(result), "detail": f"{detail_prefix}: {result or '模型返回为空'}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    def _check_wecom(self) -> Dict:
        wecom_config = runtime_config_service.get_effective_wecom_config()
        if not all(wecom_config.values()):
            return {"ok": False, "detail": "企业微信配置不完整"}

        try:
            token = wecom_service.get_access_token()
            return {"ok": bool(token), "detail": "已成功获取企业微信 access_token"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}


setup_service = SetupService()
