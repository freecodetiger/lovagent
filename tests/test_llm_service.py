import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    httpx_stub = types.ModuleType("httpx")

    class _UnusedAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("httpx.AsyncClient.post should not be called in unit tests")

    httpx_stub.AsyncClient = _UnusedAsyncClient
    sys.modules["httpx"] = httpx_stub

try:
    import app.config  # noqa: F401
except ModuleNotFoundError:
    config_stub = types.ModuleType("app.config")
    config_stub.settings = types.SimpleNamespace(
        model_provider="glm",
        zhipu_api_key="test-key",
        zhipu_model="glm-5",
        zhipu_thinking_type="disabled",
        zhipu_base_url="https://example.com",
        zhipu_web_search_enabled=True,
        zhipu_web_search_engine="search_std",
        zhipu_web_search_count=4,
        zhipu_web_search_content_size="medium",
        openai_api_key="",
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-4o-mini",
    )
    sys.modules["app.config"] = config_stub

from app.services.llm_service import GLMService


class GLMServiceTests(unittest.TestCase):
    def test_chat_completion_retries_when_only_reasoning_is_returned(self):
        service = GLMService()

        first_result = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "",
                        "reasoning_content": "先思考，正文还没来得及输出。",
                        "role": "assistant",
                    },
                }
            ]
        }
        second_result = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": "你好呀",
                        "reasoning_content": "略",
                        "role": "assistant",
                    },
                }
            ]
        }

        mocked_request = AsyncMock(side_effect=[first_result, second_result])

        with patch.object(service, "_request_completion", mocked_request):
            response = asyncio.run(
                service.chat_completion(
                    messages=[{"role": "user", "content": "你好"}],
                    max_tokens=20,
                )
            )

        self.assertEqual(response, "你好呀")
        self.assertEqual(mocked_request.await_count, 2)
        retry_payload = mocked_request.await_args_list[1].args[0]
        self.assertGreaterEqual(retry_payload["max_tokens"], 512)

    def test_chat_with_context_passes_top_p(self):
        service = GLMService()
        mocked_completion = AsyncMock(return_value="你好呀")

        with patch.object(service, "chat_completion", mocked_completion):
            response = asyncio.run(
                service.chat_with_context(
                    system_prompt="你是女朋友",
                    user_message="在吗",
                    context_messages=[{"role": "assistant", "content": "在呀"}],
                    temperature=0.88,
                    top_p=0.95,
                    max_tokens=64,
                )
            )

        self.assertEqual(response, "你好呀")
        kwargs = mocked_completion.await_args.kwargs
        self.assertEqual(kwargs["temperature"], 0.88)
        self.assertEqual(kwargs["top_p"], 0.95)
        self.assertEqual(kwargs["max_tokens"], 64)

    def test_should_use_web_search_detects_concept_and_freshness_queries(self):
        service = GLMService()

        self.assertTrue(service.should_use_web_search("AlphaFold 是什么"))
        self.assertTrue(service.should_use_web_search("帮我查一下今天比特币价格"))
        self.assertFalse(service.should_use_web_search("今天好想你呀"))

    def test_maybe_collect_web_context_returns_results_when_triggered(self):
        service = GLMService()

        with patch.object(
            service,
            "web_search",
            AsyncMock(
                return_value=[
                    {
                        "title": "AlphaFold - DeepMind",
                        "link": "https://example.com/alphafold",
                        "content": "AlphaFold 是一个蛋白质结构预测系统。",
                        "media": "DeepMind",
                        "publish_date": "2024-01-01",
                    }
                ]
            ),
        ):
            result = asyncio.run(service.maybe_collect_web_context("AlphaFold 是什么"))

        self.assertTrue(result["triggered"])
        self.assertEqual(result["query"], "AlphaFold 是什么")
        self.assertEqual(result["results"][0]["media"], "DeepMind")

    def test_web_search_uses_documented_payload_fields(self):
        service = GLMService()

        with patch.object(
            service,
            "_request_web_search",
            AsyncMock(return_value={"search_result": []}),
        ) as mocked_request:
            asyncio.run(service.web_search("AlphaFold 是什么"))

        payload = mocked_request.await_args.args[0]
        self.assertEqual(payload["search_query"], "AlphaFold 是什么")
        self.assertIn("count", payload)
        self.assertNotIn("search_count", payload)
        self.assertEqual(payload["search_intent"], False)

    def test_parse_memory_extraction_result_accepts_fenced_json(self):
        service = GLMService()

        parsed = service._parse_memory_extraction_result(
            """```json
            {
              "identity_facts": [{"key": "work_type", "value": "设计师", "confidence": 0.9, "keywords": ["设计师"]}],
              "preferences": [],
              "worries": [{"content": "最近有点焦虑", "confidence": 0.8, "keywords": ["焦虑"]}],
              "milestones": [],
              "taboos": [],
              "followups": [{"content": "明天复盘", "confidence": 0.7, "keywords": ["明天"]}],
              "short_term_summary": "最近有点焦虑，明天要复盘。",
              "emotion_trend": "焦虑",
              "user_joys": ["今天下班早"]
            }
            ```"""
        )

        self.assertEqual(parsed["identity_facts"][0]["value"], "设计师")
        self.assertEqual(parsed["worries"][0]["content"], "最近有点焦虑")
        self.assertEqual(parsed["followups"][0]["content"], "明天复盘")
        self.assertEqual(parsed["emotion_trend"], "焦虑")
        self.assertEqual(parsed["user_joys"], ["今天下班早"])

    def test_parse_memory_extraction_result_returns_empty_on_invalid_json(self):
        service = GLMService()

        parsed = service._parse_memory_extraction_result("not-json")

        self.assertEqual(parsed, service._empty_memory_extraction_result())

    def test_chat_completion_uses_manual_openai_compatible_model(self):
        service = GLMService()
        provider = types.SimpleNamespace(generate=AsyncMock(return_value=types.SimpleNamespace(content="hello")))

        with (
            patch.object(
                service,
                "_current_config",
                return_value={
                    "model_provider": "openai_compatible",
                    "openai_model_mode": "manual",
                    "openai_model": "manual-model",
                },
            ),
            patch("app.services.llm_service.get_chat_provider", return_value=provider),
        ):
            result = asyncio.run(service.chat_completion(messages=[{"role": "user", "content": "hi"}]))

        self.assertEqual(result, "hello")
        self.assertEqual(provider.generate.await_args.kwargs["model"], "manual-model")

    def test_chat_completion_uses_auto_routed_openai_model_for_task(self):
        service = GLMService()
        provider = types.SimpleNamespace(generate=AsyncMock(return_value=types.SimpleNamespace(content="memory-ok")))

        with (
            patch.object(
                service,
                "_current_config",
                return_value={
                    "model_provider": "openai_compatible",
                    "openai_model_mode": "auto",
                    "openai_model": "fallback-model",
                    "openai_models": {
                        "chat_model": "chat-model",
                        "memory_model": "memory-model",
                        "proactive_model": "proactive-model",
                    },
                },
            ),
            patch("app.services.llm_service.get_chat_provider", return_value=provider),
        ):
            result = asyncio.run(
                service.chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    task_type="memory",
                )
            )

        self.assertEqual(result, "memory-ok")
        self.assertEqual(provider.generate.await_args.kwargs["model"], "memory-model")


if __name__ == "__main__":
    unittest.main()
