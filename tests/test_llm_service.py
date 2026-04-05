import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

if "httpx" not in sys.modules:
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

if "app.config" not in sys.modules:
    config_stub = types.ModuleType("app.config")
    config_stub.settings = types.SimpleNamespace(
        zhipu_api_key="test-key",
        zhipu_model="glm-5",
        zhipu_thinking_type="disabled",
        zhipu_base_url="https://example.com",
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


if __name__ == "__main__":
    unittest.main()
