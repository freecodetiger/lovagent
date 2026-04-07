"""
模型 provider 抽象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Protocol

import httpx

from app.services.runtime_config_service import runtime_config_service


@dataclass
class ChatGenerationResult:
    content: str
    reasoning_content: str = ""
    finish_reason: str = ""
    raw: Dict | None = None


class ChatProvider(Protocol):
    async def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> ChatGenerationResult:
        raise NotImplementedError


class OpenAICompatibleChatProvider:
    """支持 OpenAI 兼容接口的 provider。"""

    def __init__(self, config: Dict):
        self.config = config

    async def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> ChatGenerationResult:
        headers = {
            "Authorization": f"Bearer {self.config['openai_api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.config["openai_model"],
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                f"{self.config['openai_base_url'].rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        choices = result.get("choices") or []
        if not choices:
            return ChatGenerationResult(content="", raw=result)

        choice = choices[0]
        message = choice.get("message") or {}
        return ChatGenerationResult(
            content=message.get("content") or "",
            reasoning_content=message.get("reasoning_content") or "",
            finish_reason=choice.get("finish_reason") or "",
            raw=result,
        )


def get_chat_provider(config: Dict | None = None) -> ChatProvider | None:
    effective_config = config or runtime_config_service.get_effective_model_config()
    provider_name = str(effective_config.get("model_provider") or "glm").strip().lower()

    if provider_name in {"openai", "openai_compatible"}:
        return OpenAICompatibleChatProvider(effective_config)

    return None
