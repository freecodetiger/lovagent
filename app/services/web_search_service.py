"""
统一 Web Search 执行层。
"""

from __future__ import annotations

import re
from typing import Dict, List

import httpx

from app.services.runtime_config_service import runtime_config_service


class TavilySearchExecutor:
    endpoint = "https://api.tavily.com/search"

    async def search(self, *, api_key: str, query: str, max_results: int) -> List[Dict[str, str]]:
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            response = await client.post(
                self.endpoint,
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "topic": "general",
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            payload = response.json()

        normalized: List[Dict[str, str]] = []
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            link = str(item.get("url") or "").strip()
            content = str(item.get("content") or item.get("raw_content") or "").strip()
            if not any([title, link, content]):
                continue
            normalized.append(
                {
                    "title": title,
                    "link": link,
                    "content": content[:500],
                    "media": "",
                    "publish_date": str(item.get("published_date") or "").strip(),
                }
            )
        return normalized


class ExaSearchExecutor:
    endpoint = "https://api.exa.ai/search"

    async def search(self, *, api_key: str, query: str, max_results: int) -> List[Dict[str, str]]:
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "type": "auto",
                    "numResults": max_results,
                    "contents": {
                        "text": True,
                        "highlights": {"numSentences": 3},
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()

        normalized: List[Dict[str, str]] = []
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            highlights = item.get("highlights") or []
            content = ""
            if isinstance(highlights, list):
                content = " ".join(str(fragment).strip() for fragment in highlights if str(fragment).strip())
            if not content:
                content = str(item.get("text") or "").strip()
            title = str(item.get("title") or "").strip()
            link = str(item.get("url") or "").strip()
            if not any([title, link, content]):
                continue
            normalized.append(
                {
                    "title": title,
                    "link": link,
                    "content": content[:500],
                    "media": str(item.get("author") or "").strip(),
                    "publish_date": str(item.get("publishedDate") or "").strip(),
                }
            )
        return normalized


class WebSearchService:
    """搜索能力统一入口，优先 Tavily，必要时回退 Exa。"""

    def __init__(self) -> None:
        self._tavily = TavilySearchExecutor()
        self._exa = ExaSearchExecutor()

    def _current_config(self) -> Dict:
        return runtime_config_service.get_effective_model_config()

    async def search(self, query: str, count: int | None = None) -> List[Dict[str, str]]:
        cleaned_query = self._build_search_query(query)
        if not cleaned_query:
            return []

        config = self._current_config()
        mode = str(config.get("search_provider_mode") or "tavily_primary_exa_fallback").strip().lower()
        max_results = max(1, min(count or 4, 8))
        tavily_key = str(config.get("tavily_api_key") or "").strip()
        exa_key = str(config.get("exa_api_key") or "").strip()

        if mode == "disabled":
            return []

        attempts: List[tuple[str, str]] = []
        if mode == "tavily":
            attempts = [("tavily", tavily_key)]
        elif mode == "exa":
            attempts = [("exa", exa_key)]
        else:
            attempts = [("tavily", tavily_key), ("exa", exa_key)]

        for provider_name, api_key in attempts:
            if not api_key:
                continue
            try:
                results = await (
                    self._tavily.search(api_key=api_key, query=cleaned_query, max_results=max_results)
                    if provider_name == "tavily"
                    else self._exa.search(api_key=api_key, query=cleaned_query, max_results=max_results)
                )
                if results:
                    return results
            except Exception as exc:
                print(f"{provider_name} search failed: {exc}")
                continue

        return []

    async def maybe_collect_web_context(self, user_message: str) -> Dict[str, object]:
        config = self._current_config()
        if not config.get("search_enabled") or not self.should_use_web_search(user_message):
            return {"enabled": bool(config.get("search_enabled")), "triggered": False, "query": "", "results": []}

        query = self._build_search_query(user_message)
        if not query:
            return {"enabled": bool(config.get("search_enabled")), "triggered": False, "query": "", "results": []}

        results = await self.search(query)
        return {
            "enabled": bool(config.get("search_enabled")),
            "triggered": bool(results),
            "query": query,
            "results": results,
        }

    def should_use_web_search(self, text: str) -> bool:
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


web_search_service = WebSearchService()
