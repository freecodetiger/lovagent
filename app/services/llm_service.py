"""
智谱 GLM-5 API 服务
"""

import httpx
from collections import defaultdict
from typing import Optional, List, Dict, Tuple
from app.config import settings


class GLMService:
    """智谱对话模型服务"""

    def __init__(self):
        self.api_key = settings.zhipu_api_key
        self.model = settings.zhipu_model
        self.thinking_type = settings.zhipu_thinking_type
        self.base_url = settings.zhipu_base_url

    async def _request_completion(self, payload: Dict) -> Dict:
        """请求对话补全接口并返回 JSON 结果。"""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _extract_message(self, result: Dict) -> Tuple[str, str, str]:
        """提取回复正文、思考内容和结束原因。"""
        choices = result.get("choices") or []
        if not choices:
            return "", "", ""

        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        reasoning_content = message.get("reasoning_content") or ""
        finish_reason = choice.get("finish_reason") or ""
        return content, reasoning_content, finish_reason

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2000,
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
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if self.thinking_type in {"enabled", "disabled"}:
            payload["thinking"] = {"type": self.thinking_type}

        result = await self._request_completion(payload)
        content, reasoning_content, finish_reason = self._extract_message(result)

        # glm-5 会先生成 reasoning_content。token 太小时，正文可能为空但 finish_reason=length。
        # 这时提升 token 再重试一次，避免返回空白回复。
        if not content and reasoning_content and finish_reason == "length":
            retry_payload = {**payload, "max_tokens": max(max_tokens * 4, 512)}
            retry_result = await self._request_completion(retry_payload)
            retry_content, _, _ = self._extract_message(retry_result)
            if retry_content:
                return retry_content

        if content:
            return content

        return ""

    async def chat_with_context(
        self,
        system_prompt: str,
        user_message: str,
        context_messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2000,
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
        )

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


# 全局服务实例
glm_service = GLMService()
