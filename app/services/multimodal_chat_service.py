"""
企业微信图片 / PDF 多模态处理服务。
"""

from __future__ import annotations

import base64
import mimetypes
import logging
from pathlib import Path
from typing import Dict, List

from app.graph.executors import save_conversation, schedule_memory_processing
from app.graph.executors.delivery import deliver_incoming_reply
from app.prompts.templates import build_dynamic_prompt
from app.services.attachment_executor_service import attachment_executor_service
from app.services.emotion_engine import emotion_engine
from app.services.llm_service import glm_service
from app.services.memory_service import memory_service
from app.services.persona_service import persona_service
from app.services.public_media_service import public_media_service
from app.services.runtime_config_service import runtime_config_service
from app.services.wecom_service import wecom_service
from app.utils.helpers import choose_natural_fallback_reply, get_current_time, get_response_constraints, is_response_too_similar

logger = logging.getLogger(__name__)


ANTI_REPEAT_RETRY_INSTRUCTION = """

# Retry Rule
- 你刚刚生成的回复和最近几轮表达太像了。
- 这次必须换一个开头、换一个回应角度和收尾。
- 保持同样的人设和情绪，但更像这次临场接话。
"""


class MultimodalChatService:
    """处理企业微信中的图片与 PDF 消息。"""

    async def process_message(self, message: Dict[str, object]) -> Dict[str, object]:
        msg_type = str(message.get("msg_type") or "").strip().lower()
        if msg_type == "image":
            return await self._process_image_message(message)
        if msg_type == "file":
            return await self._process_file_message(message)
        raise ValueError(f"Unsupported multimodal msg_type: {msg_type}")

    async def _process_image_message(self, message: Dict[str, object]) -> Dict[str, object]:
        user_id = str(message.get("from_user") or "")
        synthetic_user_message = "[图片] 用户发送了一张图片"
        model_config = runtime_config_service.get_effective_model_config()
        provider_label = str(model_config.get("provider_label") or "当前供应商").strip()

        if not model_config.get("supports_image"):
            return await self._persist_and_deliver_simple(
                user_id=user_id,
                user_message=synthetic_user_message,
                reply=f"{provider_label} 这条接入当前还没有启用图片识别，你可以先把图片里的重点内容用文字发给我，我会继续接住你。",
            )

        if not runtime_config_service.is_multimodal_configured():
            return await self._persist_and_deliver_simple(
                user_id=user_id,
                user_message=synthetic_user_message,
                reply="我这边的图片识别模型还没配置好，你也可以先用文字告诉我图片里是什么，我照样能接住你。",
            )

        return await self.process_aggregated_input(
            user_id=user_id,
            user_message=synthetic_user_message,
            attachments=[
                {
                    "msg_type": "image",
                    "media_id": message.get("media_id"),
                    "image_url": message.get("image_url"),
                }
            ],
        )

    async def _process_file_message(self, message: Dict[str, object]) -> Dict[str, object]:
        user_id = str(message.get("from_user") or "")
        file_name = str(message.get("file_name") or message.get("title") or "未命名文件").strip() or "未命名文件"
        synthetic_user_message = f"[PDF] 用户发送了文件《{file_name}》"
        model_config = runtime_config_service.get_effective_model_config()
        provider_label = str(model_config.get("provider_label") or "当前供应商").strip()

        if not file_name.lower().endswith(".pdf"):
            return await self._persist_and_deliver_simple(
                user_id=user_id,
                user_message=f"[文件] 用户发送了文件《{file_name}》",
                reply="我现在只能识别图片和 PDF，其他文件你可以换成文字、截图，或者直接发 PDF 给我。",
            )

        if not model_config.get("supports_pdf"):
            return await self._persist_and_deliver_simple(
                user_id=user_id,
                user_message=synthetic_user_message,
                reply=f"{provider_label} 这条接入当前还没有启用 PDF 识别，你可以把重点页截图发我，或者把关键内容贴成文字。",
            )

        if not runtime_config_service.is_multimodal_configured():
            return await self._persist_and_deliver_simple(
                user_id=user_id,
                user_message=synthetic_user_message,
                reply="我这边的 PDF 识别模型还没配置好，你也可以先把重点内容贴成文字，我先陪你聊。",
            )

        return await self.process_aggregated_input(
            user_id=user_id,
            user_message=synthetic_user_message,
            attachments=[
                {
                    "msg_type": "file",
                    "media_id": message.get("media_id"),
                    "file_name": file_name,
                }
            ],
        )

    async def process_aggregated_input(
        self,
        *,
        user_id: str,
        user_message: str,
        attachments: List[Dict[str, object]],
    ) -> Dict[str, object]:
        prepared_attachments = await self._build_prepared_attachments(attachments)
        return await self._run_multimodal_turn(
            user_id=user_id,
            user_message=user_message,
            prepared_attachments=prepared_attachments,
        )

    async def _run_multimodal_turn(
        self,
        *,
        user_id: str,
        user_message: str,
        prepared_attachments: List[Dict[str, object]],
    ) -> Dict[str, object]:
        await memory_service.get_or_create_user(user_id)
        persona_config = persona_service.get_persona_config()
        response_constraints = get_response_constraints(user_message, persona_config.get("response_preferences"))
        context = await memory_service.get_conversation_context(user_id)
        user_memory = await memory_service.get_user_memory(user_id, query_text=user_message)
        recent_agent_replies = await memory_service.get_recent_agent_replies(user_id, limit=3)
        context_messages = await memory_service.get_recent_messages(
            user_id,
            limit=int(response_constraints["context_limit"]),
        )

        try:
            user_emotion = await glm_service.analyze_emotion(user_message)
        except Exception as exc:
            logger.warning("多模态消息情绪分析失败，回退到默认情绪: %s", exc)
            user_emotion = {"neutral": 1.0}

        agent_emotion = await emotion_engine.update_state(user_id, user_message, user_emotion)
        system_prompt = build_dynamic_prompt(
            user_input=user_message,
            user_emotion=user_emotion,
            agent_emotion=agent_emotion,
            context=context,
            current_time=get_current_time(),
            recent_agent_replies=recent_agent_replies,
            persona_config=persona_config,
            user_profile=user_memory,
            web_search_context={"enabled": False, "triggered": False, "query": "", "results": []},
        )

        reply = ""
        try:
            reply = await attachment_executor_service.generate_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                prepared_attachments=prepared_attachments,
                context_messages=context_messages,
                temperature=0.88,
                top_p=0.93,
                max_tokens=int(response_constraints["max_tokens"]),
            )
            if reply and is_response_too_similar(reply, recent_agent_replies):
                retried_reply = await attachment_executor_service.generate_reply(
                    system_prompt=f"{system_prompt}{ANTI_REPEAT_RETRY_INSTRUCTION}",
                    user_message=user_message,
                    prepared_attachments=prepared_attachments,
                    context_messages=context_messages,
                    temperature=0.92,
                    top_p=0.95,
                    max_tokens=int(response_constraints["max_tokens"]),
                )
                reply = retried_reply or reply
        except Exception as exc:
            logger.warning("多模态回复生成失败: %s", exc)

        final_reply = reply or choose_natural_fallback_reply(user_message, user_emotion)
        conversation_id = await save_conversation(
            user_id=user_id,
            user_message=user_message,
            agent_message=final_reply,
            user_emotion=user_emotion,
            agent_emotion=agent_emotion,
        )
        schedule_memory_processing(
            wecom_user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            agent_message=final_reply,
            user_emotion=user_emotion,
            agent_emotion=agent_emotion,
        )
        delivery = await deliver_incoming_reply(to_user=user_id, content=final_reply)
        return {
            "user_message": user_message,
            "reply": final_reply,
            "conversation_id": conversation_id,
            "delivery": delivery,
        }

    async def _persist_and_deliver_simple(self, *, user_id: str, user_message: str, reply: str) -> Dict[str, object]:
        user_emotion = {"neutral": 1.0}
        agent_emotion = {"current_mood": "caring", "intensity": 45}
        conversation_id = await save_conversation(
            user_id=user_id,
            user_message=user_message,
            agent_message=reply,
            user_emotion=user_emotion,
            agent_emotion=agent_emotion,
        )
        schedule_memory_processing(
            wecom_user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            agent_message=reply,
            user_emotion=user_emotion,
            agent_emotion=agent_emotion,
        )
        delivery = await deliver_incoming_reply(to_user=user_id, content=reply)
        return {
            "user_message": user_message,
            "reply": reply,
            "conversation_id": conversation_id,
            "delivery": delivery,
        }

    async def _build_image_attachment(self, message: Dict[str, object]) -> Dict[str, object]:
        media_id = str(message.get("media_id") or "").strip()
        image_url = str(message.get("image_url") or "").strip()
        if media_id:
            content, content_type = await wecom_service.download_media(media_id)
            encoded = base64.b64encode(content).decode("utf-8")
            mime = content_type.split(";")[0].strip() or "image/jpeg"
            return {"kind": "image", "content_part": {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}}
        if image_url:
            return {"kind": "image", "content_part": {"type": "image_url", "image_url": {"url": image_url}}}
        raise ValueError("Missing image media_id and image_url")

    async def _build_pdf_attachment(self, message: Dict[str, object], file_name: str) -> Dict[str, object]:
        media_id = str(message.get("media_id") or "").strip()
        if not media_id:
            raise ValueError("Missing PDF media_id")

        content, _ = await wecom_service.download_media(media_id)
        suffix = Path(file_name).suffix or mimetypes.guess_extension("application/pdf") or ".pdf"
        filename = public_media_service.save_binary(content, suffix)
        public_url = public_media_service.build_public_url(filename)
        if not public_url:
            raise ValueError("Public base URL is unavailable for PDF hosting")
        return {
            "kind": "pdf",
            "file_name": file_name,
            "file_bytes": content,
            "public_url": public_url,
            "content_part": {"type": "file_url", "file_url": {"url": public_url}},
        }

    async def _build_prepared_attachments(self, attachments: List[Dict[str, object]]) -> List[Dict[str, object]]:
        prepared: List[Dict[str, object]] = []
        for attachment in attachments:
            msg_type = str(attachment.get("msg_type") or "").strip().lower()
            if msg_type == "image":
                prepared.append(await self._build_image_attachment(attachment))
            elif msg_type == "file":
                file_name = str(attachment.get("file_name") or "").strip() or "未命名文件.pdf"
                prepared.append(await self._build_pdf_attachment(attachment, file_name))
        return prepared


multimodal_chat_service = MultimodalChatService()
