"""
首次安装向导服务
"""

from typing import Dict

import httpx

from app.config import settings
from app.services.llm_service import glm_service
from app.services.runtime_config_service import runtime_config_service
from app.services.tunnel_service import tunnel_service
from app.services.wecom_service import wecom_service


class SetupService:
    """聚合初始化状态与校验逻辑。"""

    def get_status(self) -> Dict:
        status = runtime_config_service.get_status_payload()
        if not status["current"]["public_base_url"]:
            tunnel_service.ensure_started()

        status["tunnel"] = tunnel_service.get_status()
        if status["tunnel"]["public_url"] and not status["current"]["public_base_url"]:
            status = runtime_config_service.get_status_payload()
            status["tunnel"] = tunnel_service.get_status()
        return status

    async def validate(self) -> Dict:
        status = self.get_status()
        checks = {
            "local_health": await self._check_local_health(),
            "public_health": await self._check_public_health(),
            "model": await self._check_model(),
            "wecom": self._check_wecom(),
        }
        checks["callback"] = {
            "ok": bool(runtime_config_service.get_effective_public_base_url()),
            "detail": runtime_config_service.get_callback_url(),
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

    async def _check_public_health(self) -> Dict:
        public_base_url = runtime_config_service.get_effective_public_base_url()
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
        if not model_config["zhipu_api_key"]:
            return {"ok": False, "detail": "未配置 GLM API Key"}

        try:
            result = await glm_service.chat_completion(
                [{"role": "user", "content": "你好，请只回复“ok”"}],
                temperature=0.1,
                top_p=0.9,
                max_tokens=24,
            )
            return {"ok": bool(result), "detail": result or "模型返回为空"}
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
