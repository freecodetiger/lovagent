"""
统一大模型调用服务。
"""

from collections import defaultdict
import json
import re
from typing import Dict, List, Optional

from app.providers.model_provider import extract_generation_result, get_chat_provider
from app.services.web_search_service import web_search_service
from app.services.runtime_config_service import runtime_config_service


class GLMService:
    """统一对话与多模态调用入口。"""

    def __init__(self):
        pass

    def _current_config(self) -> Dict:
        return runtime_config_service.get_effective_model_config()

    def _current_provider_name(self) -> str:
        return str(self._current_config().get("provider_transport") or "glm").strip().lower()

    def _resolve_chat_model(self, config: Dict, task_type: str) -> str:
        routed = config.get("text_models") or config.get("openai_models") or {}
        task_key = {
            "chat": "chat_model",
            "memory": "memory_model",
            "proactive": "proactive_model",
        }.get(task_type, "chat_model")
        return str(routed.get(task_key) or config.get("text_model") or config.get("openai_model") or "").strip()

    async def _request_completion(self, payload: Dict[str, object], *, api_key: str | None = None):
        config = self._current_config()
        provider = get_chat_provider(config)
        if provider is None:
            raise ValueError(f"Unsupported model provider: {self._current_provider_name()}")

        return await provider.generate(
            payload["messages"],
            model=str(payload.get("model") or "").strip(),
            temperature=float(payload.get("temperature", 0.7)),
            top_p=float(payload.get("top_p", 0.9)),
            max_tokens=int(payload.get("max_tokens", 2000)),
            api_key_override=api_key,
        )

    async def _request_web_search(self, payload: Dict[str, object]):
        return await web_search_service.search(
            str(payload.get("search_query") or "").strip(),
            count=int(payload.get("count") or 4),
        )

    def _extract_result_fields(self, response) -> tuple[str, str, str]:
        if isinstance(response, dict):
            result = extract_generation_result(response)
            return result.content or "", result.reasoning_content or "", result.finish_reason or ""

        content = getattr(response, "content", "") or ""
        reasoning_content = getattr(response, "reasoning_content", "") or ""
        finish_reason = getattr(response, "finish_reason", "") or ""
        return content, reasoning_content, finish_reason

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2000,
        task_type: str = "chat",
    ) -> str:
        """
        调用 GLM-5 对话补全 API

        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            top_p: Top-p 参数
            max_tokens: 最大生成 token 数

        Returns:
            生成的回复内容
        """
        config = self._current_config()
        payload = {
            "messages": messages,
            "model": self._resolve_chat_model(config, task_type),
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        result = await self._request_completion(payload)
        content, reasoning_content, finish_reason = self._extract_result_fields(result)

        # 部分模型会先生成 reasoning_content。token 太小时，正文可能为空但 finish_reason=length。
        # 这时提升 token 再重试一次，避免返回空白回复。
        if not content and reasoning_content and finish_reason == "length":
            retry_payload = dict(payload)
            retry_payload["max_tokens"] = max(max_tokens * 4, 512)
            retry_result = await self._request_completion(retry_payload)
            retry_content, _, _ = self._extract_result_fields(retry_result)
            if retry_content:
                return retry_content

        if content:
            return content

        return ""

    async def chat_multimodal(
        self,
        *,
        system_prompt: str,
        user_message: str,
        content_parts: List[Dict[str, object]],
        context_messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        """按当前供应商能力调用多模态模型处理图片或 PDF。"""
        config = self._current_config()
        provider = get_chat_provider(config)
        if provider is None:
            raise ValueError("Multimodal provider is not available")

        multimodal_api_key = str(config.get("multimodal_api_key") or "").strip()
        multimodal_model = str(config.get("multimodal_model") or "").strip()
        if config.get("supports_multimodal") is False or not multimodal_api_key or not multimodal_model:
            raise ValueError("Multimodal model is not configured")

        messages: List[Dict[str, object]] = [{"role": "system", "content": system_prompt}]
        if context_messages:
            messages.extend(context_messages)
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message},
                    *content_parts,
                ],
            }
        )

        payload = {
            "messages": messages,
            "model": multimodal_model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        result = await self._request_completion(payload, api_key=multimodal_api_key)
        content, reasoning_content, finish_reason = self._extract_result_fields(result)
        if not content and reasoning_content and finish_reason == "length":
            retry_payload = dict(payload)
            retry_payload["max_tokens"] = max(max_tokens * 2, 1024)
            retry_result = await self._request_completion(retry_payload, api_key=multimodal_api_key)
            retry_content, _, _ = self._extract_result_fields(retry_result)
            if retry_content:
                return retry_content

        return content or ""

    async def chat_with_context(
        self,
        system_prompt: str,
        user_message: str,
        context_messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2000,
        task_type: str = "chat",
    ) -> str:
        """
        带上下文的对话

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            context_messages: 上下文消息列表
            temperature: 温度参数
            top_p: Top-p 参数

        Returns:
            生成的回复内容
        """
        messages = [{"role": "system", "content": system_prompt}]

        # 添加上下文消息
        if context_messages:
            messages.extend(context_messages)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return await self.chat_completion(
            messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            task_type=task_type,
        )

    async def web_search(
        self,
        query: str,
        search_engine: Optional[str] = None,
        search_count: Optional[int] = None,
        content_size: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        del search_engine, content_size
        payload = {
            "search_query": query,
            "count": search_count or self._current_config().get("web_search_count") or 4,
            "search_intent": False,
        }
        result = await self._request_web_search(payload)
        if isinstance(result, dict):
            return result.get("search_result") or []
        return result

    async def maybe_collect_web_context(self, user_message: str) -> Dict[str, object]:
        """根据用户消息判断是否需要联网检索，并返回搜索结果。"""
        config = self._current_config()
        search_enabled = bool(config.get("search_enabled")) or bool(config.get("web_search_enabled"))
        if not search_enabled or not self.should_use_web_search(user_message):
            return {"enabled": search_enabled, "triggered": False, "query": "", "results": []}

        query = self._build_search_query(user_message)
        if not query:
            return {"enabled": search_enabled, "triggered": False, "query": "", "results": []}

        results = await self.web_search(query)
        return {
            "enabled": search_enabled,
            "triggered": bool(results),
            "query": query,
            "results": results,
        }

    def should_use_web_search(self, text: str) -> bool:
        """启发式判断当前消息是否需要联网检索。"""
        return web_search_service.should_use_web_search(text)

    def _build_search_query(self, text: str) -> str:
        return web_search_service._build_search_query(text)

    async def analyze_emotion(self, text: str) -> Dict[str, float]:
        """
        使用本地规则快速估计情绪，避免额外模型请求。

        Args:
            text: 待分析的文本

        Returns:
            情绪分析结果
        """
        cleaned = text.strip()
        if not cleaned:
            return {"neutral": 1.0}

        keyword_map = {
            "happiness": ["开心", "高兴", "哈哈", "嘿嘿", "耶", "好耶", "太好了", "不错", "爽"],
            "sadness": ["难过", "伤心", "委屈", "想哭", "失落", "低落", "崩溃"],
            "anger": ["生气", "气死", "烦死", "火大", "无语", "离谱", "服了"],
            "anxiety": ["焦虑", "担心", "慌", "害怕", "紧张", "忐忑"],
            "love": ["想你", "爱你", "喜欢你", "抱抱", "晚安", "早安", "亲亲", "宝贝"],
            "tired": ["累", "困", "疲惫", "不想动", "睡了", "想睡", "没精神"],
            "stress": ["压力", "加班", "忙", "好多事", "烦", "工作", "ddl", "截止"],
        }

        scores = defaultdict(float)
        lowered = cleaned.lower()

        for emotion, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in lowered:
                    scores[emotion] += 1.0

        if not scores:
            return {"neutral": 1.0}

        total = sum(scores.values())
        result = {emotion: round(score / total, 3) for emotion, score in scores.items()}
        if "neutral" not in result:
            result["neutral"] = round(max(0.0, 1 - sum(result.values())), 3)
        return result

    async def extract_memory_facts(
        self,
        user_message: str,
        agent_message: str,
        existing_memory: Optional[Dict] = None,
        short_term_memory: Optional[Dict] = None,
        recent_messages: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, object]:
        """提取结构化记忆信息。"""
        if not user_message.strip():
            return self._empty_memory_extraction_result()

        recent_context = recent_messages or []
        existing_memory = existing_memory or {}
        short_term_memory = short_term_memory or {}

        prompt = f"""
你是一个恋爱陪伴 Agent 的记忆提炼器。请从下面这轮对话和已有记忆中，提炼适合长期记住或短期跟进的信息。

要求：
1. 只输出 JSON，不要输出解释，不要加 markdown 代码块。
2. 没有把握的信息不要编造。
3. identity_facts / preferences 使用对象数组，字段必须包含 key、value、confidence。
4. worries / milestones / taboos / followups 使用对象数组，字段必须包含 content、confidence。
5. keywords 可以选填数组；没有就输出空数组。
6. short_term_summary 要控制在 80 字以内。
7. emotion_trend 只允许输出：升温、平稳、低落、焦虑、疲惫、开心、暧昧、混合、未知。

输出 JSON 结构：
{{
  "identity_facts": [{{"key": "", "value": "", "confidence": 0.0, "keywords": []}}],
  "preferences": [{{"key": "", "value": "", "confidence": 0.0, "keywords": []}}],
  "worries": [{{"content": "", "confidence": 0.0, "keywords": []}}],
  "milestones": [{{"content": "", "confidence": 0.0, "keywords": []}}],
  "taboos": [{{"content": "", "confidence": 0.0, "keywords": []}}],
  "followups": [{{"content": "", "confidence": 0.0, "keywords": []}}],
  "short_term_summary": "",
  "emotion_trend": "",
  "user_joys": []
}}

已有长期记忆：
{json.dumps(existing_memory, ensure_ascii=False)}

已有短期记忆：
{json.dumps(short_term_memory, ensure_ascii=False)}

最近几轮消息：
{json.dumps(recent_context[-6:], ensure_ascii=False)}

当前用户消息：
{user_message}

当前 Agent 回复：
{agent_message}
""".strip()

        try:
            raw = await self.chat_completion(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "请输出 JSON。"},
                ],
                temperature=0.1,
                top_p=0.7,
                max_tokens=700,
                task_type="memory",
            )
        except Exception:
            return self._empty_memory_extraction_result()

        return self._parse_memory_extraction_result(raw)

    def _parse_memory_extraction_result(self, raw: str) -> Dict[str, object]:
        if not raw.strip():
            return self._empty_memory_extraction_result()

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.replace("```json", "```")
            parts = cleaned.split("```")
            cleaned = next((part.strip() for part in parts if part.strip().startswith("{")), cleaned)

        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            cleaned = match.group(0)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return self._empty_memory_extraction_result()

        return {
            "identity_facts": self._normalize_fact_items(payload.get("identity_facts"), "key", "value"),
            "preferences": self._normalize_fact_items(payload.get("preferences"), "key", "value"),
            "worries": self._normalize_text_items(payload.get("worries")),
            "milestones": self._normalize_text_items(payload.get("milestones")),
            "taboos": self._normalize_text_items(payload.get("taboos")),
            "followups": self._normalize_text_items(payload.get("followups")),
            "short_term_summary": str(payload.get("short_term_summary") or "").strip()[:120],
            "emotion_trend": str(payload.get("emotion_trend") or "").strip()[:20],
            "user_joys": self._normalize_scalar_list(payload.get("user_joys")),
        }

    def _normalize_fact_items(self, value: object, key_field: str, value_field: str) -> List[Dict[str, object]]:
        if not isinstance(value, list):
            return []

        normalized: List[Dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            key = str(item.get(key_field) or "").strip()
            content = str(item.get(value_field) or "").strip()
            if not key or not content:
                continue
            normalized.append(
                {
                    "key": key,
                    "value": content,
                    "confidence": self._normalize_confidence(item.get("confidence")),
                    "keywords": self._normalize_scalar_list(item.get("keywords")),
                }
            )
        return normalized

    def _normalize_text_items(self, value: object) -> List[Dict[str, object]]:
        if not isinstance(value, list):
            return []

        normalized: List[Dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            normalized.append(
                {
                    "content": content,
                    "confidence": self._normalize_confidence(item.get("confidence")),
                    "keywords": self._normalize_scalar_list(item.get("keywords")),
                }
            )
        return normalized

    def _normalize_scalar_list(self, value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_confidence(self, value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.5
        return max(0.0, min(1.0, number))

    def _empty_memory_extraction_result(self) -> Dict[str, object]:
        return {
            "identity_facts": [],
            "preferences": [],
            "worries": [],
            "milestones": [],
            "taboos": [],
            "followups": [],
            "short_term_summary": "",
            "emotion_trend": "",
            "user_joys": [],
        }


# 全局服务实例
glm_service = GLMService()
