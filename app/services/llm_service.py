"""
智谱 GLM-5 API 服务
"""

import httpx
from typing import Optional, List, Dict
from app.config import settings


class GLMService:
    """智谱 GLM-5 服务"""

    def __init__(self):
        self.api_key = settings.zhipu_api_key
        self.model = settings.zhipu_model
        self.base_url = settings.zhipu_base_url

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
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

        # 提取回复内容
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]

        return ""

    async def chat_with_context(
        self,
        system_prompt: str,
        user_message: str,
        context_messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        带上下文的对话

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            context_messages: 上下文消息列表
            temperature: 温度参数

        Returns:
            生成的回复内容
        """
        messages = [{"role": "system", "content": system_prompt}]

        # 添加上下文消息
        if context_messages:
            messages.extend(context_messages)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return await self.chat_completion(messages, temperature=temperature)

    async def analyze_emotion(self, text: str) -> Dict[str, float]:
        """
        分析文本情绪

        Args:
            text: 待分析的文本

        Returns:
            情绪分析结果
        """
        system_prompt = """你是一个情绪分析助手。请分析用户文本中的情绪，返回以下情绪的概率分布：
- happiness: 开心/喜悦
- sadness: 难过/悲伤
- anger: 生气/愤怒
- anxiety: 焦虑/担忧
- neutral: 平静/中性
- love: 爱/思念
- tired: 疲惫/累
- stress: 压力/压力

请以 JSON 格式返回，例如: {"happiness": 0.3, "sadness": 0.1, ...}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析这段文本的情绪: {text}"},
        ]

        response = await self.chat_completion(messages, temperature=0.1)

        # 尝试解析 JSON
        try:
            import json
            # 尝试从回复中提取 JSON
            if "{" in response and "}" in response:
                json_str = response[response.find("{"): response.rfind("}") + 1]
                return json.loads(json_str)
        except Exception:
            pass

        # 默认返回中性情绪
        return {"neutral": 1.0}


# 全局服务实例
glm_service = GLMService()