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


def _coerce_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        fragments: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())
        return "\n".join(fragments)

    return ""


def extract_generation_result(result: Dict) -> ChatGenerationResult:
    choices = result.get("choices") or []
    if not choices:
        return ChatGenerationResult(content="", raw=result)

    choice = choices[0]
    message = choice.get("message") or {}
    return ChatGenerationResult(
        content=_coerce_content_to_text(message.get("content")),
        reasoning_content=str(message.get("reasoning_content") or ""),
        finish_reason=str(choice.get("finish_reason") or ""),
        raw=result,
    )


class ChatProvider(Protocol):
    async def generate(
        self,
        messages: List[Dict[str, object]],
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        api_key_override: str | None = None,
    ) -> ChatGenerationResult:
        raise NotImplementedError


class ZhipuChatProvider:
    """智谱原生 chat/completions provider。"""

    def __init__(self, config: Dict):
        self.config = config

    async def generate(
        self,
        messages: List[Dict[str, object]],
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        api_key_override: str | None = None,
    ) -> ChatGenerationResult:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if self.config.get("zhipu_thinking_type") in {"enabled", "disabled"} and not api_key_override:
            payload["thinking"] = {"type": self.config["zhipu_thinking_type"]}

        headers = {
            "Authorization": f"Bearer {api_key_override or self.config['provider_api_key']}",
            "Content-Type": "application/json",
        }
        base_url = str(self.config["provider_base_url"]).rstrip("/")
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        return extract_generation_result(result)


class OpenAICompatibleChatProvider:
    """支持 OpenAI 兼容接口的 provider。"""

    def __init__(self, config: Dict):
        self.config = config

    async def generate(
        self,
        messages: List[Dict[str, object]],
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        api_key_override: str | None = None,
    ) -> ChatGenerationResult:
        headers = {
            "Authorization": f"Bearer {api_key_override or self.config['provider_api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                f"{self.config['provider_base_url'].rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        return extract_generation_result(result)


def get_chat_provider(config: Dict | None = None) -> ChatProvider | None:
    effective_config = config or runtime_config_service.get_effective_model_config()
    provider_name = str(
        effective_config.get("provider_transport")
        or effective_config.get("model_provider")
        or "glm"
    ).strip().lower()

    if provider_name in {"glm"}:
        return ZhipuChatProvider(effective_config)

    if provider_name in {"openai", "openai_compatible"}:
        return OpenAICompatibleChatProvider(effective_config)

    return None
