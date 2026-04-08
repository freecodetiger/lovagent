"""
模型供应商目录与能力描述。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable
from urllib.parse import urlparse

from app.config import settings


@dataclass(frozen=True)
class ProviderPreset:
    provider_id: str
    label: str
    transport: str
    default_base_url: str
    default_text_model: str
    default_multimodal_model: str
    default_document_model: str
    supports_multimodal: bool
    supports_image: bool
    supports_pdf: bool
    pdf_execution_mode: str
    docs_url: str

    @property
    def default_routed_models(self) -> Dict[str, str]:
        return {
            "chat_model": self.default_text_model,
            "memory_model": self.default_text_model,
            "proactive_model": self.default_text_model,
        }

    def to_status_payload(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["default_routed_models"] = self.default_routed_models
        return payload


PROVIDER_PRESETS: Dict[str, ProviderPreset] = {
    "zhipu": ProviderPreset(
        provider_id="zhipu",
        label="智谱 GLM",
        transport="glm",
        default_base_url=settings.zhipu_base_url.rstrip("/"),
        default_text_model="glm-5",
        default_multimodal_model="glm-4.6v",
        default_document_model="glm-4.6v",
        supports_multimodal=True,
        supports_image=True,
        supports_pdf=True,
        pdf_execution_mode="chat_file_url",
        docs_url="https://open.bigmodel.cn/",
    ),
    "openai": ProviderPreset(
        provider_id="openai",
        label="OpenAI",
        transport="openai_compatible",
        default_base_url="https://api.openai.com/v1",
        default_text_model="gpt-4o-mini",
        default_multimodal_model="gpt-4o-mini",
        default_document_model="gpt-4o-mini",
        supports_multimodal=True,
        supports_image=True,
        supports_pdf=True,
        pdf_execution_mode="responses_file_url",
        docs_url="https://platform.openai.com/docs/overview",
    ),
    "qwen": ProviderPreset(
        provider_id="qwen",
        label="阿里通义千问",
        transport="openai_compatible",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_text_model="qwen-plus",
        default_multimodal_model="qwen-vl-max-latest",
        default_document_model="qwen-doc-turbo",
        supports_multimodal=True,
        supports_image=True,
        supports_pdf=True,
        pdf_execution_mode="qwen_file_id",
        docs_url="https://help.aliyun.com/zh/model-studio/",
    ),
    "deepseek": ProviderPreset(
        provider_id="deepseek",
        label="DeepSeek",
        transport="openai_compatible",
        default_base_url="https://api.deepseek.com/v1",
        default_text_model="deepseek-chat",
        default_multimodal_model="",
        default_document_model="",
        supports_multimodal=False,
        supports_image=False,
        supports_pdf=False,
        pdf_execution_mode="unsupported",
        docs_url="https://api-docs.deepseek.com/",
    ),
}


def list_provider_presets() -> Iterable[ProviderPreset]:
    return PROVIDER_PRESETS.values()


def get_provider_preset(provider_id: str | None) -> ProviderPreset:
    normalized = str(provider_id or "").strip().lower()
    return PROVIDER_PRESETS.get(normalized) or PROVIDER_PRESETS["zhipu"]


def infer_provider_id(model_config: Dict | None) -> str:
    source = model_config if isinstance(model_config, dict) else {}

    explicit = str(source.get("provider_id") or source.get("model_provider") or "").strip().lower()
    if explicit in PROVIDER_PRESETS:
        return explicit
    if explicit in {"glm"}:
        return "zhipu"

    base_url = str(source.get("provider_base_url") or source.get("openai_base_url") or "").strip().lower()
    host = urlparse(base_url).netloc.lower()
    if "bigmodel.cn" in host:
        return "zhipu"
    if "dashscope.aliyuncs.com" in host:
        return "qwen"
    if "deepseek.com" in host:
        return "deepseek"
    if "openai.com" in host:
        return "openai"

    if explicit in {"openai", "openai_compatible"}:
        return "openai"

    return "zhipu"
