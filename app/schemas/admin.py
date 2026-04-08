"""
管理后台接口的 Pydantic 模型
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class PersonaCorePayload(BaseModel):
    role: str = ""
    persona_summary: str = ""
    aesthetic: str = ""
    lifestyle: str = ""
    opening_style: str = ""
    signature_style: str = ""
    emoji_style: str = ""


class AgentPersonaPayload(BaseModel):
    display_name: str = "小甜"
    persona_core: PersonaCorePayload = Field(default_factory=PersonaCorePayload)
    personality_metrics: Dict[str, int] = Field(default_factory=dict)
    interests: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)
    topics_to_avoid: List[str] = Field(default_factory=list)
    recommended_topics: List[str] = Field(default_factory=list)
    response_rules: List[str] = Field(default_factory=list)
    response_preferences: Dict[str, int] = Field(default_factory=dict)


class PreviewRequest(BaseModel):
    user_message: str
    channel: Optional[str] = None
    external_user_id: Optional[str] = None
    wecom_user_id: Optional[str] = None
    draft_config: Optional[AgentPersonaPayload] = None


class UserMemoryPayload(BaseModel):
    nickname: str = ""
    avatar_url: str = ""
    basic_info: Dict[str, object] = Field(default_factory=dict)
    emotional_patterns: Dict[str, object] = Field(default_factory=dict)
    relationship_milestones: List[object] = Field(default_factory=list)
    preferences: Dict[str, object] = Field(default_factory=dict)


class ScheduledWindowPayload(BaseModel):
    key: str
    label: str = ""
    enabled: bool = True
    time: str = "09:30"


class QuietHoursPayload(BaseModel):
    enabled: bool = True
    start: str = "23:00"
    end: str = "09:00"


class ProactiveChatPayload(BaseModel):
    enabled: bool = False
    target_channel: str = "wecom"
    target_external_user_id: str = ""
    target_wecom_user_id: str = ""
    scheduled_windows: List[ScheduledWindowPayload] = Field(default_factory=list)
    inactivity_trigger_hours: int = 6
    quiet_hours: QuietHoursPayload = Field(default_factory=QuietHoursPayload)
    max_messages_per_day: int = 4
    min_interval_minutes: int = 180
    tone_hint: str = ""


class ProactiveChatActionRequest(BaseModel):
    channel: Optional[str] = None
    external_user_id: Optional[str] = None
    wecom_user_id: Optional[str] = None


class SetupOpenAIModelsPayload(BaseModel):
    chat_model: str = ""
    memory_model: str = ""
    proactive_model: str = ""


class SetupModelPayload(BaseModel):
    model_provider: str = "glm"
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-5"
    zhipu_thinking_type: str = "disabled"
    multimodal_api_key: str = ""
    multimodal_model: str = "glm-4.6v"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model_mode: str = "manual"
    openai_model: str = ""
    openai_models: SetupOpenAIModelsPayload = Field(default_factory=SetupOpenAIModelsPayload)


class SetupWeComPayload(BaseModel):
    corp_id: str = ""
    agent_id: str = ""
    secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    public_base_url: str = ""


class SetupNapCatPayload(BaseModel):
    ws_url: str = ""
    ws_token: str = ""


class SetupAdminPayload(BaseModel):
    password: str = ""
