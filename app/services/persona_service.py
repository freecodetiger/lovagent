"""
全局人设配置服务
"""

from ast import literal_eval
from typing import Dict, Optional

from sqlalchemy.exc import OperationalError

from app.models.admin import AgentConfig
from app.models.database import SessionLocal
from app.prompts.base_persona import build_base_persona, get_default_persona_config, normalize_persona_config


DEFAULT_PERSONA_CONFIG_KEY = "default_agent_persona"


class PersonaService:
    """管理全局 Agent 人设配置。"""

    def get_persona_config(self) -> Dict:
        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(AgentConfig)
                    .filter(AgentConfig.config_key == DEFAULT_PERSONA_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                return self._build_payload(get_default_persona_config())
            if not record:
                return self._build_payload(get_default_persona_config())

            persona_core = dict(record.persona_core or {})
            persona_core.pop("interests", None)
            persona_core.pop("values", None)
            response_preferences = self._extract_response_preferences(persona_core)
            persona_core.pop("_response_preferences", None)
            payload = {
                "display_name": record.display_name,
                "persona_core": persona_core,
                "personality_metrics": record.personality_metrics or {},
                "topics_to_avoid": record.topics_to_avoid or [],
                "recommended_topics": record.recommended_topics or [],
                "response_rules": record.response_rules or [],
                "response_preferences": response_preferences,
            }

            extra = self._extract_extra_fields(record)
            payload.update(extra)
            return self._build_payload(payload, updated_at=record.updated_at.isoformat() if record.updated_at else None)
        finally:
            db.close()

    def save_persona_config(self, config: Dict) -> Dict:
        normalized = normalize_persona_config(config)
        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(AgentConfig)
                    .filter(AgentConfig.config_key == DEFAULT_PERSONA_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                db.rollback()
                record = None
            if not record:
                record = AgentConfig(config_key=DEFAULT_PERSONA_CONFIG_KEY)
                db.add(record)

            persona_core = dict(normalized["persona_core"])
            persona_core["interests"] = list(normalized["interests"])
            persona_core["values"] = list(normalized["values"])
            persona_core["_response_preferences"] = dict(normalized["response_preferences"])

            record.display_name = normalized["display_name"]
            record.persona_core = persona_core
            record.persona_text = build_base_persona(normalized)
            record.personality_metrics = normalized["personality_metrics"]
            record.topics_to_avoid = normalized["topics_to_avoid"]
            record.recommended_topics = normalized["recommended_topics"]
            record.response_rules = normalized["response_rules"]

            db.commit()
            db.refresh(record)
            return self.get_persona_config()
        finally:
            db.close()

    def render_base_persona(self, config: Optional[Dict] = None) -> str:
        return build_base_persona(config or self.get_persona_config())

    def _build_payload(self, config: Dict, updated_at: Optional[str] = None) -> Dict:
        normalized = normalize_persona_config(config)
        normalized["updated_at"] = updated_at
        normalized["base_persona_text"] = build_base_persona(normalized)
        return normalized

    def _extract_extra_fields(self, record: AgentConfig) -> Dict:
        persona_core = record.persona_core or {}
        return {
            "interests": persona_core.get("interests") or [],
            "values": persona_core.get("values") or [],
        }

    def _extract_response_preferences(self, persona_core: Dict) -> Dict:
        raw = persona_core.get("_response_preferences")
        if isinstance(raw, dict):
            return dict(raw)

        if isinstance(raw, str):
            try:
                parsed = literal_eval(raw)
            except (ValueError, SyntaxError):
                return {}
            if isinstance(parsed, dict):
                return parsed

        return {}


persona_service = PersonaService()
