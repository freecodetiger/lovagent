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
from app.services.provider_catalog import get_provider_preset, infer_provider_id, list_provider_presets


RUNTIME_CONFIG_KEY = "setup_runtime_config"

DEFAULT_RUNTIME_CONFIG = {
    "model": {
        "provider_id": "zhipu",
        "provider_api_key": "",
        "provider_base_url": "",
        "text_model_override": "",
        "multimodal_model_override": "",
        "document_model_override": "",
        "search_provider_mode": "tavily_primary_exa_fallback",
        "tavily_api_key": "",
        "exa_api_key": "",
        "model_provider": "glm",
        "zhipu_api_key": "",
        "zhipu_model": "glm-5",
        "zhipu_thinking_type": "disabled",
        "multimodal_api_key": "",
        "multimodal_model": "glm-4.6v",
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

        defaults["provider_id"] = str(source.get("provider_id", defaults["provider_id"]) or defaults["provider_id"])
        defaults["provider_api_key"] = str(source.get("provider_api_key", defaults["provider_api_key"]) or "")
        defaults["provider_base_url"] = str(source.get("provider_base_url", defaults["provider_base_url"]) or "")
        defaults["text_model_override"] = str(source.get("text_model_override", defaults["text_model_override"]) or "")
        defaults["multimodal_model_override"] = str(
            source.get("multimodal_model_override", defaults["multimodal_model_override"]) or ""
        )
        defaults["document_model_override"] = str(source.get("document_model_override", defaults["document_model_override"]) or "")
        defaults["search_provider_mode"] = str(source.get("search_provider_mode", defaults["search_provider_mode"]) or defaults["search_provider_mode"])
        defaults["tavily_api_key"] = str(source.get("tavily_api_key", defaults["tavily_api_key"]) or "")
        defaults["exa_api_key"] = str(source.get("exa_api_key", defaults["exa_api_key"]) or "")
        defaults["model_provider"] = str(source.get("model_provider", defaults["model_provider"]) or defaults["model_provider"])
        defaults["zhipu_api_key"] = str(source.get("zhipu_api_key", defaults["zhipu_api_key"]) or "")
        defaults["zhipu_model"] = str(source.get("zhipu_model", defaults["zhipu_model"]) or defaults["zhipu_model"])
        defaults["zhipu_thinking_type"] = str(
            source.get("zhipu_thinking_type", defaults["zhipu_thinking_type"]) or defaults["zhipu_thinking_type"]
        )
        defaults["multimodal_api_key"] = str(source.get("multimodal_api_key", defaults["multimodal_api_key"]) or "")
        defaults["multimodal_model"] = str(
            source.get("multimodal_model", defaults["multimodal_model"]) or defaults["multimodal_model"]
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
        provider_id = infer_provider_id(config)
        preset = get_provider_preset(provider_id)

        provider_api_key = str(config.get("provider_api_key") or "").strip()
        if not provider_api_key:
            if provider_id == "zhipu":
                provider_api_key = str(config.get("zhipu_api_key") or settings.zhipu_api_key or "").strip()
            else:
                provider_api_key = str(config.get("openai_api_key") or settings.openai_api_key or "").strip()

        provider_base_url = str(config.get("provider_base_url") or "").strip().rstrip("/")
        if not provider_base_url:
            if preset.transport == "glm":
                provider_base_url = str(settings.zhipu_base_url).strip().rstrip("/")
            else:
                provider_base_url = str(
                    config.get("openai_base_url") or settings.openai_base_url or preset.default_base_url
                ).strip().rstrip("/")
        if not provider_base_url:
            provider_base_url = preset.default_base_url.rstrip("/")

        if provider_id == "zhipu":
            text_override = str(config.get("text_model_override") or config.get("zhipu_model") or "").strip()
        else:
            text_override = str(config.get("text_model_override") or config.get("openai_model") or "").strip()
        text_model = text_override or preset.default_text_model

        routed_defaults = preset.default_routed_models
        legacy_routed = config.get("openai_models") or {}
        legacy_mode = str(config.get("openai_model_mode") or "manual").strip().lower()
        if provider_id == "zhipu":
            text_models = {
                "chat_model": text_model,
                "memory_model": text_model,
                "proactive_model": text_model,
            }
        elif legacy_mode == "auto" and any(str(legacy_routed.get(key) or "").strip() for key in routed_defaults):
            text_models = {
                "chat_model": str(legacy_routed.get("chat_model") or routed_defaults["chat_model"]).strip(),
                "memory_model": str(legacy_routed.get("memory_model") or routed_defaults["memory_model"]).strip(),
                "proactive_model": str(legacy_routed.get("proactive_model") or routed_defaults["proactive_model"]).strip(),
            }
        else:
            base_model = text_model or preset.default_text_model
            text_models = {
                "chat_model": base_model,
                "memory_model": base_model,
                "proactive_model": base_model,
            }

        multimodal_api_key = str(config.get("multimodal_api_key") or "").strip() or provider_api_key
        if provider_id == "zhipu":
            multimodal_api_key = multimodal_api_key or str(settings.zhipu_multimodal_api_key or settings.zhipu_api_key or "").strip()

        multimodal_override = str(config.get("multimodal_model_override") or "").strip()
        legacy_multimodal = str(config.get("multimodal_model") or "").strip() if provider_id == "zhipu" else ""
        multimodal_model = ""
        if preset.supports_multimodal:
            multimodal_model = multimodal_override or legacy_multimodal or preset.default_multimodal_model
        document_model = str(config.get("document_model_override") or "").strip() or preset.default_document_model

        tavily_api_key = str(config.get("tavily_api_key") or settings.tavily_api_key or "").strip()
        exa_api_key = str(config.get("exa_api_key") or settings.exa_api_key or "").strip()
        search_provider_mode = str(
            config.get("search_provider_mode") or settings.search_provider_mode or "tavily_primary_exa_fallback"
        ).strip()
        search_enabled = bool(
            settings.zhipu_web_search_enabled and (
                (search_provider_mode in {"tavily_primary_exa_fallback", "tavily"} and tavily_api_key)
                or (search_provider_mode in {"tavily_primary_exa_fallback", "exa"} and exa_api_key)
            )
        )

        return {
            "provider_id": provider_id,
            "provider_label": preset.label,
            "provider_transport": preset.transport,
            "provider_docs_url": preset.docs_url,
            "provider_api_key": provider_api_key,
            "provider_base_url": provider_base_url,
            "default_text_model": preset.default_text_model,
            "default_multimodal_model": preset.default_multimodal_model,
            "default_document_model": preset.default_document_model,
            "text_model": text_model or preset.default_text_model,
            "text_models": text_models,
            "document_model": document_model,
            "supports_multimodal": preset.supports_multimodal,
            "supports_image": preset.supports_image,
            "supports_pdf": preset.supports_pdf,
            "pdf_execution_mode": preset.pdf_execution_mode,
            "search_provider_mode": search_provider_mode,
            "search_enabled": search_enabled,
            "tavily_api_key": tavily_api_key,
            "exa_api_key": exa_api_key,
            "model_provider": preset.transport,
            "zhipu_api_key": config["zhipu_api_key"] or settings.zhipu_api_key,
            "zhipu_model": config["zhipu_model"] or settings.zhipu_model,
            "zhipu_thinking_type": config["zhipu_thinking_type"] or settings.zhipu_thinking_type,
            "multimodal_api_key": multimodal_api_key,
            "multimodal_model": multimodal_model,
            "zhipu_base_url": provider_base_url if preset.transport == "glm" else settings.zhipu_base_url,
            "zhipu_web_search_enabled": settings.zhipu_web_search_enabled,
            "zhipu_web_search_engine": settings.zhipu_web_search_engine,
            "zhipu_web_search_count": settings.zhipu_web_search_count,
            "zhipu_web_search_content_size": settings.zhipu_web_search_content_size,
            "openai_api_key": provider_api_key if preset.transport == "openai_compatible" else (config["openai_api_key"] or settings.openai_api_key),
            "openai_base_url": provider_base_url if preset.transport == "openai_compatible" else (config["openai_base_url"] or settings.openai_base_url),
            "openai_model_mode": "auto",
            "openai_model": text_model or settings.openai_model,
            "openai_models": text_models,
        }

    def is_model_configured(self) -> bool:
        model = self.get_effective_model_config()
        return bool(
            str(model.get("provider_api_key") or "").strip()
            and str(model.get("provider_base_url") or "").strip()
            and str(model.get("text_model") or "").strip()
        )

    def is_multimodal_configured(self) -> bool:
        model = self.get_effective_model_config()
        return bool(
            model.get("supports_multimodal")
            and str(model.get("multimodal_api_key") or "").strip()
            and str(model.get("multimodal_model") or "").strip()
        )

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
            "provider_catalog": [preset.to_status_payload() for preset in list_provider_presets()],
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
                "provider_id": effective_model["provider_id"],
                "provider_label": effective_model["provider_label"],
                "provider_transport": effective_model["provider_transport"],
                "provider_base_url": effective_model["provider_base_url"],
                "default_text_model": effective_model["default_text_model"],
                "default_multimodal_model": effective_model["default_multimodal_model"],
                "default_document_model": effective_model["default_document_model"],
                "text_model": effective_model["text_model"],
                "text_models": deepcopy(effective_model["text_models"]),
                "document_model": effective_model["document_model"],
                "supports_multimodal": bool(effective_model["supports_multimodal"]),
                "supports_image": bool(effective_model["supports_image"]),
                "supports_pdf": bool(effective_model["supports_pdf"]),
                "pdf_execution_mode": effective_model["pdf_execution_mode"],
                "search_provider_mode": effective_model["search_provider_mode"],
                "search_enabled": bool(effective_model["search_enabled"]),
                "model_provider": effective_model["provider_id"],
                "zhipu_model": effective_model["zhipu_model"],
                "multimodal_model": effective_model["multimodal_model"],
                "openai_model_mode": "auto",
                "openai_base_url": effective_model["provider_base_url"],
                "openai_model": effective_model["text_model"],
                "openai_models": deepcopy(effective_model["text_models"]),
                "public_base_url": effective_public_base_url,
                "callback_url": self.get_callback_url(),
                "wecom_corp_id": effective_wecom["corp_id"],
                "wecom_agent_id": effective_wecom["agent_id"],
                "has_provider_api_key": bool(effective_model["provider_api_key"]),
                "has_tavily_api_key": bool(effective_model["tavily_api_key"]),
                "has_exa_api_key": bool(effective_model["exa_api_key"]),
                "has_zhipu_api_key": bool(effective_model["zhipu_api_key"]),
                "has_multimodal_api_key": bool(effective_model["multimodal_api_key"]),
                "multimodal_configured": self.is_multimodal_configured(),
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
                    "provider_id": infer_provider_id(raw["model"]),
                    "provider_base_url": str(raw["model"].get("provider_base_url") or "").strip(),
                    "has_provider_api_key": bool(raw["model"].get("provider_api_key")),
                    "search_provider_mode": str(raw["model"].get("search_provider_mode") or "tavily_primary_exa_fallback"),
                    "has_tavily_api_key": bool(raw["model"].get("tavily_api_key")),
                    "has_exa_api_key": bool(raw["model"].get("exa_api_key")),
                    "model_provider": raw["model"]["model_provider"],
                    "zhipu_model": raw["model"]["zhipu_model"],
                    "multimodal_model": raw["model"]["multimodal_model"],
                    "openai_model_mode": "auto",
                    "openai_base_url": raw["model"]["openai_base_url"],
                    "openai_model": raw["model"]["openai_model"],
                    "openai_models": deepcopy(raw["model"]["openai_models"]),
                    "has_zhipu_api_key": bool(raw["model"]["zhipu_api_key"]),
                    "has_multimodal_api_key": bool(raw["model"]["multimodal_api_key"]),
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
