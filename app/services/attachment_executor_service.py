"""
附件理解执行层。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import httpx

from app.providers.model_provider import extract_generation_result, get_chat_provider
from app.services.runtime_config_service import runtime_config_service


PreparedAttachment = Dict[str, object]


def _extract_responses_output_text(payload: Dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    fragments: List[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())
    return "\n".join(fragments)


class AttachmentExecutorService:
    """按供应商能力路由图片 / PDF 理解执行。"""

    def _current_config(self) -> Dict:
        return runtime_config_service.get_effective_model_config()

    async def generate_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        prepared_attachments: List[PreparedAttachment],
        context_messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        if not prepared_attachments:
            raise ValueError("No prepared attachments were provided")

        if any(str(item.get("kind") or "") == "pdf" for item in prepared_attachments):
            return await self._generate_pdf_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                prepared_attachments=prepared_attachments,
                context_messages=context_messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

        return await self._generate_image_reply(
            system_prompt=system_prompt,
            user_message=user_message,
            prepared_attachments=prepared_attachments,
            context_messages=context_messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    async def _generate_image_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        prepared_attachments: List[PreparedAttachment],
        context_messages: Optional[List[Dict[str, str]]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> str:
        config = self._current_config()
        provider = get_chat_provider(config)
        if provider is None:
            raise ValueError("Image executor is unavailable for current provider")

        content_parts = [item["content_part"] for item in prepared_attachments if item.get("content_part")]
        messages: List[Dict[str, object]] = [{"role": "system", "content": system_prompt}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": [{"type": "text", "text": user_message}, *content_parts]})

        result = await provider.generate(
            messages,
            model=str(config.get("multimodal_model") or ""),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            api_key_override=str(config.get("multimodal_api_key") or "").strip() or None,
        )
        return result.content or ""

    async def _generate_pdf_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        prepared_attachments: List[PreparedAttachment],
        context_messages: Optional[List[Dict[str, str]]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> str:
        config = self._current_config()
        pdf_mode = str(config.get("pdf_execution_mode") or "unsupported").strip().lower()

        if pdf_mode == "chat_file_url":
            return await self._generate_image_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                prepared_attachments=prepared_attachments,
                context_messages=context_messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

        if pdf_mode == "responses_file_url":
            return await self._generate_openai_pdf_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                prepared_attachments=prepared_attachments,
                context_messages=context_messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

        if pdf_mode == "qwen_file_id":
            return await self._generate_qwen_pdf_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                prepared_attachments=prepared_attachments,
                context_messages=context_messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

        raise ValueError("PDF executor is unavailable for current provider")

    async def _generate_openai_pdf_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        prepared_attachments: List[PreparedAttachment],
        context_messages: Optional[List[Dict[str, str]]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> str:
        config = self._current_config()
        pdf_urls = [
            str(item.get("public_url") or "").strip()
            for item in prepared_attachments
            if str(item.get("kind") or "") == "pdf" and str(item.get("public_url") or "").strip()
        ]
        if not pdf_urls:
            raise ValueError("Missing public PDF URL for OpenAI PDF execution")

        input_messages: List[Dict[str, object]] = [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]}
        ]
        for message in context_messages or []:
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "").strip()
            if content:
                input_messages.append({"role": role, "content": [{"type": "input_text", "text": content}]})

        user_content: List[Dict[str, object]] = [{"type": "input_text", "text": user_message}]
        for pdf_url in pdf_urls:
            user_content.append({"type": "input_file", "file_url": pdf_url})
        input_messages.append({"role": "user", "content": user_content})

        payload = {
            "model": str(config.get("document_model") or config.get("multimodal_model") or ""),
            "input": input_messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=90.0, trust_env=False) as client:
            response = await client.post(
                f"{str(config.get('provider_base_url') or '').rstrip('/')}/responses",
                headers={
                    "Authorization": f"Bearer {config['provider_api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        return _extract_responses_output_text(result)

    async def _generate_qwen_pdf_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        prepared_attachments: List[PreparedAttachment],
        context_messages: Optional[List[Dict[str, str]]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> str:
        config = self._current_config()
        provider = get_chat_provider(config)
        if provider is None:
            raise ValueError("Qwen PDF executor is unavailable")

        pdf_attachment = next(
            (
                item for item in prepared_attachments
                if str(item.get("kind") or "") == "pdf" and isinstance(item.get("file_bytes"), (bytes, bytearray))
            ),
            None,
        )
        if pdf_attachment is None:
            raise ValueError("Missing PDF bytes for Qwen PDF execution")

        file_id = await self._upload_qwen_pdf(
            file_bytes=bytes(pdf_attachment["file_bytes"]),
            file_name=str(pdf_attachment.get("file_name") or "document.pdf"),
            api_key=str(config.get("provider_api_key") or ""),
            base_url=str(config.get("provider_base_url") or ""),
        )

        messages: List[Dict[str, object]] = [
            {"role": "system", "content": f"fileid://{file_id}"},
            {"role": "system", "content": system_prompt},
        ]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_message})

        result = await provider.generate(
            messages,
            model=str(config.get("document_model") or ""),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return result.content or ""

    async def _upload_qwen_pdf(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        api_key: str,
        base_url: str,
    ) -> str:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/files",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"purpose": "file-extract"},
                files={"file": (file_name, file_bytes, "application/pdf")},
            )
            response.raise_for_status()
            payload = response.json()
        file_id = str(payload.get("id") or "").strip()
        if not file_id:
            raise ValueError("Qwen file upload did not return file id")
        return file_id


attachment_executor_service = AttachmentExecutorService()
