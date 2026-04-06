"""
智谱 GLM-5 API 服务
"""

import httpx
from collections import defaultdict
import re
from typing import Optional, List, Dict, Tuple
from app.services.runtime_config_service import runtime_config_service


class GLMService:
    """智谱对话模型服务"""

    def __init__(self):
        pass

    def _current_config(self) -> Dict:
        return runtime_config_service.get_effective_model_config()

    async def _request_completion(self, payload: Dict) -> Dict:
        """请求对话补全接口并返回 JSON 结果。"""
        config = self._current_config()
        url = f"{config['zhipu_base_url']}/chat/completions"

        headers = {
            "Authorization": f"Bearer {config['zhipu_api_key']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _request_web_search(self, payload: Dict) -> Dict:
        """请求智谱 Web Search 接口并返回 JSON 结果。"""
        config = self._current_config()
        url = f"{config['zhipu_base_url']}/web_search"

        headers = {
            "Authorization": f"Bearer {config['zhipu_api_key']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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
        config = self._current_config()
        payload = {
            "model": config["zhipu_model"],
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if config["zhipu_thinking_type"] in {"enabled", "disabled"}:
            payload["thinking"] = {"type": config["zhipu_thinking_type"]}

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

    async def web_search(
        self,
        query: str,
        search_engine: Optional[str] = None,
        search_count: Optional[int] = None,
        content_size: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """调用智谱 Web Search 接口。"""
        cleaned_query = self._build_search_query(query)
        if not cleaned_query:
            return []

        config = self._current_config()
        payload = {
            "search_query": cleaned_query,
            "search_engine": search_engine or config["zhipu_web_search_engine"],
            "search_intent": False,
            "count": search_count or config["zhipu_web_search_count"],
            "content_size": content_size or config["zhipu_web_search_content_size"],
        }
        result = await self._request_web_search(payload)
        items = result.get("search_result") or result.get("results") or []
        if not isinstance(items, list):
            return []

        normalized: List[Dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or item.get("url") or "").strip()
            content = str(item.get("content") or item.get("snippet") or item.get("text") or "").strip()
            media = str(item.get("media") or item.get("site_name") or "").strip()
            publish_date = str(item.get("publish_date") or item.get("date") or "").strip()

            if not any([title, content, link]):
                continue

            normalized.append(
                {
                    "title": title,
                    "link": link,
                    "content": content,
                    "media": media,
                    "publish_date": publish_date,
                }
            )

        return normalized

    async def maybe_collect_web_context(self, user_message: str) -> Dict[str, object]:
        """根据用户消息判断是否需要联网检索，并返回搜索结果。"""
        config = self._current_config()
        if not config["zhipu_web_search_enabled"] or not self.should_use_web_search(user_message):
            return {"enabled": config["zhipu_web_search_enabled"], "triggered": False, "query": "", "results": []}

        query = self._build_search_query(user_message)
        if not query:
            return {"enabled": config["zhipu_web_search_enabled"], "triggered": False, "query": "", "results": []}

        results = await self.web_search(query)
        return {
            "enabled": config["zhipu_web_search_enabled"],
            "triggered": bool(results),
            "query": query,
            "results": results,
        }

    def should_use_web_search(self, text: str) -> bool:
        """启发式判断当前消息是否需要联网检索。"""
        cleaned = text.strip()
        if len(cleaned) < 2:
            return False

        explicit_markers = (
            "查一下",
            "搜一下",
            "搜索",
            "帮我查",
            "帮我搜",
            "是什么",
            "什么意思",
            "科普",
            "介绍一下",
            "解释一下",
            "这个词",
            "这个概念",
            "这个人",
            "这个公司",
            "这个品牌",
            "这是什么",
            "谁是",
            "谁啊",
        )
        freshness_markers = (
            "最新",
            "最近",
            "今天",
            "刚刚",
            "新闻",
            "发布",
            "价格",
            "汇率",
            "股价",
            "比赛",
            "比分",
            "天气",
        )
        emotional_chat_markers = (
            "想你",
            "爱你",
            "抱抱",
            "亲亲",
            "在吗",
            "晚安",
            "早安",
            "宝贝",
            "陪我",
        )
        question_markers = ("?", "？", "吗", "呢", "么", "怎么", "为什么")

        if any(marker in cleaned for marker in explicit_markers):
            return True
        if any(marker in cleaned for marker in emotional_chat_markers):
            return False
        if any(marker in cleaned for marker in freshness_markers):
            return True

        ascii_tokens = re.findall(r"[A-Za-z][A-Za-z0-9.+_/-]{1,24}", cleaned)
        if ascii_tokens and (any(marker in cleaned for marker in question_markers) or len(cleaned) <= 32):
            return True

        concept_patterns = (
            r".{0,12}叫.{0,18}吗",
            r".{0,18}啥意思",
            r".{0,18}是什么梗",
            r".{0,18}是什么东西",
        )
        return any(re.search(pattern, cleaned) for pattern in concept_patterns)

    def _build_search_query(self, text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:80]

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
