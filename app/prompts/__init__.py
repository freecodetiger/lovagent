"""
Prompt 模板模块
"""

from app.prompts.base_persona import AGENT_PERSONA, PERSONALITY_MATRIX, EMOTIONAL_RESPOND_RULES
from app.prompts.templates import (
    BASE_PERSONA,
    build_dynamic_prompt,
    build_morning_greeting,
    build_night_greeting,
)

__all__ = [
    "AGENT_PERSONA",
    "PERSONALITY_MATRIX",
    "EMOTIONAL_RESPOND_RULES",
    "BASE_PERSONA",
    "build_dynamic_prompt",
    "build_morning_greeting",
    "build_night_greeting",
]