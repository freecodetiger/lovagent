"""
运行时配置服务
"""

from copy import deepcopy
from typing import Dict, Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.models.admin import RuntimeConfig
from app.models.database import SessionLocal


RUNTIME_CONFIG_KEY = "setup_runtime_config"

DEFAULT_RUNTIME_CONFIG = {
    "model": {
        "model_provider": "glm",
        "zhipu_api_key": "",
        "zhipu_model": "glm-5",
        "zhipu_thinking_type": "disabled",
        "openai_api_key": "",
        "openai_base_url": "",
        "openai_model_mode": "manual",
        "openai_model": "",
        "openai_models": {
            "chat_model": "",
            "memory_model": "",
            "proactive_model": "",
        },
    },
    "wecom": {
        "corp_id": "",
        "agent_id": "",
        "secret": "",
        "token": "",
        "encoding_aes_key": "",
    },
    "napcat": {
        "ws_url": "",
        "ws_token": "",
    },
    "deployment": {
        "public_base_url": "",
    },
    "admin": {
        "password": "",
    },
}


class RuntimeConfigService:
    """读写安装向导运行时配置。"""

    def _normalize_model_section(self, incoming: Dict | None) -> Dict:
        defaults = deepcopy(DEFAULT_RUNTIME_CONFIG["model"])
        source = incoming if isinstance(incoming, dict) else {}

        defaults["model_provider"] = str(source.get("model_provider", defaults["model_provider"]) or defaults["model_provider"])
        defaults["zhipu_api_key"] = str(source.get("zhipu_api_key", defaults["zhipu_api_key"]) or "")
        defaults["zhipu_model"] = str(source.get("zhipu_model", defaults["zhipu_model"]) or defaults["zhipu_model"])
        defaults["zhipu_thinking_type"] = str(
            source.get("zhipu_thinking_type", defaults["zhipu_thinking_type"]) or defaults["zhipu_thinking_type"]
        )
        defaults["openai_api_key"] = str(source.get("openai_api_key", defaults["openai_api_key"]) or "")
        defaults["openai_base_url"] = str(source.get("openai_base_url", defaults["openai_base_url"]) or "")
        defaults["openai_model_mode"] = str(
            source.get("openai_model_mode", defaults["openai_model_mode"]) or defaults["openai_model_mode"]
        )
        defaults["openai_model"] = str(source.get("openai_model", defaults["openai_model"]) or "")

        incoming_models = source.get("openai_models") if isinstance(source.get("openai_models"), dict) else {}
        defaults["openai_models"] = {
            "chat_model": str(incoming_models.get("chat_model") or ""),
            "memory_model": str(incoming_models.get("memory_model") or ""),
            "proactive_model": str(incoming_models.get("proactive_model") or ""),
        }
        return defaults

    def get_config(self) -> Dict:
        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(RuntimeConfig)
                    .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                return deepcopy(DEFAULT_RUNTIME_CONFIG)

            if not record:
                return deepcopy(DEFAULT_RUNTIME_CONFIG)

            merged = deepcopy(DEFAULT_RUNTIME_CONFIG)
            value = record.config_value or {}
            for section, defaults in DEFAULT_RUNTIME_CONFIG.items():
                incoming = value.get(section) if isinstance(value, dict) else {}
                if section == "model":
                    merged[section] = self._normalize_model_section(incoming if isinstance(incoming, dict) else {})
                elif isinstance(incoming, dict):
                    merged[section].update({key: incoming.get(key, fallback) for key, fallback in defaults.items()})
            return merged
        finally:
            db.close()

    def save_section(self, section: str, payload: Dict) -> Dict:
        if section not in DEFAULT_RUNTIME_CONFIG:
            raise ValueError(f"Unknown config section: {section}")

        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(RuntimeConfig)
                    .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                db.rollback()
                record = None

            if not record:
                record = RuntimeConfig(config_key=RUNTIME_CONFIG_KEY, config_value=deepcopy(DEFAULT_RUNTIME_CONFIG))
                db.add(record)

            current = deepcopy(record.config_value) if isinstance(record.config_value, dict) else deepcopy(DEFAULT_RUNTIME_CONFIG)
            current.setdefault(section, {})
            current[section].update(payload)
            record.config_value = current
            flag_modified(record, "config_value")
            db.commit()
            db.refresh(record)
            return self.get_config()
        finally:
            db.close()

    def get_effective_model_config(self) -> Dict:
        config = self.get_config()["model"]
        openai_model = config["openai_model"] or settings.openai_model
        openai_models = {
            "chat_model": str((config.get("openai_models") or {}).get("chat_model") or openai_model),
            "memory_model": str((config.get("openai_models") or {}).get("memory_model") or openai_model),
            "proactive_model": str((config.get("openai_models") or {}).get("proactive_model") or openai_model),
        }
        return {
            "model_provider": config["model_provider"] or settings.model_provider,
            "zhipu_api_key": config["zhipu_api_key"] or settings.zhipu_api_key,
            "zhipu_model": config["zhipu_model"] or settings.zhipu_model,
            "zhipu_thinking_type": config["zhipu_thinking_type"] or settings.zhipu_thinking_type,
            "zhipu_base_url": settings.zhipu_base_url,
            "zhipu_web_search_enabled": settings.zhipu_web_search_enabled,
            "zhipu_web_search_engine": settings.zhipu_web_search_engine,
            "zhipu_web_search_count": settings.zhipu_web_search_count,
            "zhipu_web_search_content_size": settings.zhipu_web_search_content_size,
            "openai_api_key": config["openai_api_key"] or settings.openai_api_key,
            "openai_base_url": config["openai_base_url"] or settings.openai_base_url,
            "openai_model_mode": config["openai_model_mode"] or "manual",
            "openai_model": openai_model,
            "openai_models": openai_models,
        }

    def is_model_configured(self) -> bool:
        model = self.get_effective_model_config()
        provider = str(model.get("model_provider") or "glm").strip().lower()
        if provider in {"", "glm"}:
            return bool(model["zhipu_api_key"] and model["zhipu_model"])

        if provider in {"openai", "openai_compatible"}:
            if not (model["openai_api_key"] and model["openai_base_url"]):
                return False

            mode = str(model.get("openai_model_mode") or "manual").strip().lower()
            if mode == "auto":
                routed = model.get("openai_models") or {}
                return all(
                    str(routed.get(key) or "").strip()
                    for key in ("chat_model", "memory_model", "proactive_model")
                )
            return bool(str(model.get("openai_model") or "").strip())

        return False

    def get_effective_wecom_config(self) -> Dict:
        config = self.get_config()["wecom"]
        return {
            "corp_id": config["corp_id"] or settings.wecom_corp_id,
            "agent_id": config["agent_id"] or settings.wecom_agent_id,
            "secret": config["secret"] or settings.wecom_secret,
            "token": config["token"] or settings.wecom_token,
            "encoding_aes_key": config["encoding_aes_key"] or settings.wecom_encoding_aes_key,
        }

    def get_effective_napcat_config(self) -> Dict:
        config = self.get_config()["napcat"]
        return {
            "ws_url": str(config.get("ws_url") or settings.napcat_ws_url).strip(),
            "ws_token": str(config.get("ws_token") or settings.napcat_ws_token).strip(),
        }

    def get_effective_public_base_url(self) -> str:
        deployment = self.get_config()["deployment"]
        return str(deployment.get("public_base_url") or settings.public_base_url).strip()

    def get_effective_admin_password(self) -> str:
        admin = self.get_config()["admin"]
        return str(admin.get("password") or settings.admin_password).strip()

    def get_callback_url(self) -> str:
        public_base_url = self.get_effective_public_base_url()
        if public_base_url:
            return f"{public_base_url.rstrip('/')}/wecom/callback"
        return f"http://{settings.server_host}:{settings.server_port}/wecom/callback"

    def is_setup_complete(self) -> bool:
        wecom = self.get_effective_wecom_config()
        public_base_url = self.get_effective_public_base_url()
        admin_password = self.get_effective_admin_password()
        return all(
            [
                self.is_model_configured(),
                wecom["corp_id"],
                wecom["agent_id"],
                wecom["secret"],
                wecom["token"],
                wecom["encoding_aes_key"],
                public_base_url,
                admin_password,
            ]
        )

    def get_status_payload(self) -> Dict:
        raw = self.get_config()
        effective_model = self.get_effective_model_config()
        effective_wecom = self.get_effective_wecom_config()
        effective_napcat = self.get_effective_napcat_config()
        effective_public_base_url = self.get_effective_public_base_url()
        effective_admin_password = self.get_effective_admin_password()

        return {
            "setup_completed": self.is_setup_complete(),
            "sections": {
                "model_configured": self.is_model_configured(),
                "wecom_configured": all(
                    [
                        effective_wecom["corp_id"],
                        effective_wecom["agent_id"],
                        effective_wecom["secret"],
                        effective_wecom["token"],
                        effective_wecom["encoding_aes_key"],
                    ]
                ),
                "napcat_configured": bool(effective_napcat["ws_url"]),
                "admin_configured": bool(effective_admin_password),
                "deployment_configured": bool(effective_public_base_url),
            },
            "current": {
                "model_provider": effective_model["model_provider"],
                "zhipu_model": effective_model["zhipu_model"],
                "openai_model_mode": effective_model["openai_model_mode"],
                "openai_base_url": effective_model["openai_base_url"],
                "openai_model": effective_model["openai_model"],
                "openai_models": deepcopy(effective_model["openai_models"]),
                "public_base_url": effective_public_base_url,
                "callback_url": self.get_callback_url(),
                "wecom_corp_id": effective_wecom["corp_id"],
                "wecom_agent_id": effective_wecom["agent_id"],
                "has_zhipu_api_key": bool(effective_model["zhipu_api_key"]),
                "has_openai_api_key": bool(effective_model["openai_api_key"]),
                "has_wecom_secret": bool(effective_wecom["secret"]),
                "has_wecom_token": bool(effective_wecom["token"]),
                "has_wecom_encoding_aes_key": bool(effective_wecom["encoding_aes_key"]),
                "napcat_ws_url": effective_napcat["ws_url"],
                "has_napcat_ws_token": bool(effective_napcat["ws_token"]),
                "has_admin_password": bool(effective_admin_password),
            },
            "raw": {
                "model": {
                    "model_provider": raw["model"]["model_provider"],
                    "zhipu_model": raw["model"]["zhipu_model"],
                    "openai_model_mode": raw["model"]["openai_model_mode"],
                    "openai_base_url": raw["model"]["openai_base_url"],
                    "openai_model": raw["model"]["openai_model"],
                    "openai_models": deepcopy(raw["model"]["openai_models"]),
                    "has_zhipu_api_key": bool(raw["model"]["zhipu_api_key"]),
                    "has_openai_api_key": bool(raw["model"]["openai_api_key"]),
                },
                "wecom": {
                    "corp_id": raw["wecom"]["corp_id"],
                    "agent_id": raw["wecom"]["agent_id"],
                    "has_secret": bool(raw["wecom"]["secret"]),
                    "has_token": bool(raw["wecom"]["token"]),
                    "has_encoding_aes_key": bool(raw["wecom"]["encoding_aes_key"]),
                },
                "napcat": {
                    "ws_url": raw["napcat"]["ws_url"],
                    "has_ws_token": bool(raw["napcat"]["ws_token"]),
                },
                "deployment": {
                    "public_base_url": raw["deployment"]["public_base_url"],
                },
                "admin": {
                    "has_password": bool(raw["admin"]["password"]),
                },
            },
        }


runtime_config_service = RuntimeConfigService()
