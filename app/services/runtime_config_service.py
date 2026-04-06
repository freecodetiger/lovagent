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
        "zhipu_api_key": "",
        "zhipu_model": "glm-5",
        "zhipu_thinking_type": "disabled",
    },
    "wecom": {
        "corp_id": "",
        "agent_id": "",
        "secret": "",
        "token": "",
        "encoding_aes_key": "",
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
                if isinstance(incoming, dict):
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
        return {
            "zhipu_api_key": config["zhipu_api_key"] or settings.zhipu_api_key,
            "zhipu_model": config["zhipu_model"] or settings.zhipu_model,
            "zhipu_thinking_type": config["zhipu_thinking_type"] or settings.zhipu_thinking_type,
            "zhipu_base_url": settings.zhipu_base_url,
            "zhipu_web_search_enabled": settings.zhipu_web_search_enabled,
            "zhipu_web_search_engine": settings.zhipu_web_search_engine,
            "zhipu_web_search_count": settings.zhipu_web_search_count,
            "zhipu_web_search_content_size": settings.zhipu_web_search_content_size,
        }

    def get_effective_wecom_config(self) -> Dict:
        config = self.get_config()["wecom"]
        return {
            "corp_id": config["corp_id"] or settings.wecom_corp_id,
            "agent_id": config["agent_id"] or settings.wecom_agent_id,
            "secret": config["secret"] or settings.wecom_secret,
            "token": config["token"] or settings.wecom_token,
            "encoding_aes_key": config["encoding_aes_key"] or settings.wecom_encoding_aes_key,
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
        model = self.get_effective_model_config()
        wecom = self.get_effective_wecom_config()
        public_base_url = self.get_effective_public_base_url()
        admin_password = self.get_effective_admin_password()
        return all(
            [
                model["zhipu_api_key"],
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
        effective_public_base_url = self.get_effective_public_base_url()
        effective_admin_password = self.get_effective_admin_password()

        return {
            "setup_completed": self.is_setup_complete(),
            "sections": {
                "model_configured": bool(effective_model["zhipu_api_key"]),
                "wecom_configured": all(
                    [
                        effective_wecom["corp_id"],
                        effective_wecom["agent_id"],
                        effective_wecom["secret"],
                        effective_wecom["token"],
                        effective_wecom["encoding_aes_key"],
                    ]
                ),
                "admin_configured": bool(effective_admin_password),
                "deployment_configured": bool(effective_public_base_url),
            },
            "current": {
                "zhipu_model": effective_model["zhipu_model"],
                "public_base_url": effective_public_base_url,
                "callback_url": self.get_callback_url(),
                "wecom_corp_id": effective_wecom["corp_id"],
                "wecom_agent_id": effective_wecom["agent_id"],
                "has_zhipu_api_key": bool(effective_model["zhipu_api_key"]),
                "has_wecom_secret": bool(effective_wecom["secret"]),
                "has_wecom_token": bool(effective_wecom["token"]),
                "has_wecom_encoding_aes_key": bool(effective_wecom["encoding_aes_key"]),
                "has_admin_password": bool(effective_admin_password),
            },
            "raw": {
                "model": {
                    "zhipu_model": raw["model"]["zhipu_model"],
                    "has_zhipu_api_key": bool(raw["model"]["zhipu_api_key"]),
                },
                "wecom": {
                    "corp_id": raw["wecom"]["corp_id"],
                    "agent_id": raw["wecom"]["agent_id"],
                    "has_secret": bool(raw["wecom"]["secret"]),
                    "has_token": bool(raw["wecom"]["token"]),
                    "has_encoding_aes_key": bool(raw["wecom"]["encoding_aes_key"]),
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
