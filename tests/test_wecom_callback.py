import asyncio
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

try:
    from fastapi import HTTPException
    from app.routers import wecom
    from wechatpy.enterprise.crypto import WeChatCrypto
    IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - 取决于环境依赖是否已安装
    HTTPException = Exception
    wecom = None
    WeChatCrypto = None
    IMPORT_ERROR = exc


class DummyRequest:
    async def body(self):
        return b"<xml>encrypted</xml>"


@unittest.skipIf(wecom is None, f"missing dependency: {IMPORT_ERROR}")
class WeComCallbackVerifyTests(unittest.TestCase):
    def test_wecom_callback_verify_returns_plaintext(self):
        with patch.object(wecom.wecom_service, "verify_callback", return_value="decrypted-echo") as mocked_verify:
            response = asyncio.run(
                wecom.wecom_callback_verify(
                    msg_signature="sig",
                    timestamp="123",
                    nonce="nonce",
                    echostr="echo",
                )
            )

        mocked_verify.assert_called_once_with(
            msg_signature="sig",
            timestamp="123",
            nonce="nonce",
            echostr="echo",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.decode(), "decrypted-echo")

    def test_wecom_callback_verify_requires_echostr(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                wecom.wecom_callback_verify(
                    msg_signature="sig",
                    timestamp="123",
                    nonce="nonce",
                    echostr=None,
                )
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Missing echostr")

    def test_wecom_callback_verify_accepts_real_wecom_signature(self):
        config = {
            "corp_id": "ww2a6262fa052ccac3",
            "agent_id": "1000002",
            "secret": "secret-test",
            "token": "LoIsXTYpesDSdiGk7GS1nP7L7PAhTOy",
            "encoding_aes_key": "JuV3lxQO5mdnPQ7RmS0ocowz5CV2xoRuNmyd7NyEjjs",
        }
        crypto = WeChatCrypto(config["token"], config["encoding_aes_key"], config["corp_id"])
        encrypted_xml = crypto.encrypt_message("plain-echo", nonce="nonce-123", timestamp="1712476800")
        root = ET.fromstring(encrypted_xml)

        with patch(
            "app.services.wecom_service.runtime_config_service.get_effective_wecom_config",
            return_value=config,
        ):
            response = asyncio.run(
                wecom.wecom_callback_verify(
                    msg_signature=root.findtext("MsgSignature"),
                    timestamp=root.findtext("TimeStamp"),
                    nonce=root.findtext("Nonce"),
                    echostr=root.findtext("Encrypt"),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.decode(), "plain-echo")


@unittest.skipIf(wecom is None, f"missing dependency: {IMPORT_ERROR}")
class WeComCallbackHandlerTests(unittest.TestCase):
    def _run_handler(
        self,
        *,
        user_content="今天有点累",
        user_emotion=None,
        recent_replies=None,
        chat_side_effect=None,
        persona_config=None,
    ):
        user_emotion = user_emotion or {"neutral": 1.0}
        recent_replies = recent_replies or []
        persona_config = persona_config or {"response_preferences": {}}
        chat_mock = AsyncMock(side_effect=chat_side_effect)
        send_mock = AsyncMock(return_value={"errcode": 0})
        save_mock = AsyncMock(return_value=123)
        schedule_mock = patch.object(wecom.memory_service, "schedule_memory_processing")

        with (
            patch.object(wecom.wecom_service, "decrypt_message", return_value="<xml />"),
            patch.object(
                wecom.wecom_service,
                "parse_message",
                return_value={
                    "msg_type": "text",
                    "from_user": "user-1",
                    "content": user_content,
                },
            ),
            patch.object(wecom.wecom_service, "send_text_message", send_mock),
            patch.object(wecom.memory_service, "get_or_create_user", AsyncMock(return_value={"id": 1})),
            patch.object(wecom.memory_service, "get_conversation_context", AsyncMock(return_value={"today_chat_count": 1})),
            patch.object(wecom.memory_service, "get_recent_messages", AsyncMock(return_value=[{"role": "assistant", "content": "之前聊过"}])),
            patch.object(wecom.memory_service, "get_recent_agent_replies", AsyncMock(return_value=recent_replies)),
            patch.object(wecom.memory_service, "get_user_memory", AsyncMock(return_value=None)) as get_memory_mock,
            patch.object(wecom.memory_service, "save_conversation", save_mock),
            schedule_mock as mocked_schedule,
            patch.object(wecom.glm_service, "analyze_emotion", AsyncMock(return_value=user_emotion)),
            patch.object(wecom.glm_service, "chat_with_context", chat_mock),
            patch.object(wecom.glm_service, "maybe_collect_web_context", AsyncMock(return_value={"triggered": False, "query": "", "results": []})),
            patch.object(wecom.emotion_engine, "update_state", AsyncMock(return_value={"current_mood": "caring", "intensity": 55})),
            patch.object(wecom.persona_service, "get_persona_config", return_value=persona_config),
        ):
            response = asyncio.run(
                wecom.wecom_callback_handler(
                    request=DummyRequest(),
                    msg_signature="sig",
                    timestamp="123",
                    nonce="nonce",
                )
            )

        return response, chat_mock, send_mock, save_mock, mocked_schedule, get_memory_mock

    def test_handler_regenerates_when_reply_is_too_similar(self):
        response, chat_mock, send_mock, save_mock, schedule_mock, get_memory_mock = self._run_handler(
            user_emotion={"tired": 0.9},
            recent_replies=["我在呢，你接着说，我有在听。"],
            chat_side_effect=[
                "我在呢[抱抱]，你继续说，我认真听着。",
                "听着就觉得你今天扛了很多，要不要慢慢和我说？",
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.decode(), "success")
        self.assertEqual(chat_mock.await_count, 2)
        second_prompt = chat_mock.await_args_list[1].kwargs["system_prompt"]
        self.assertIn("Retry Rule", second_prompt)
        self.assertEqual(
            send_mock.await_args.args[1],
            "听着就觉得你今天扛了很多，要不要慢慢和我说？",
        )
        self.assertEqual(
            save_mock.await_args.kwargs["agent_message"],
            "听着就觉得你今天扛了很多，要不要慢慢和我说？",
        )
        get_memory_mock.assert_awaited_once_with("wecom", "user-1", query_text="今天有点累")
        schedule_mock.assert_called_once()
        self.assertEqual(schedule_mock.call_args.kwargs["conversation_id"], 123)

    def test_handler_uses_natural_fallback_after_generation_failures(self):
        _, chat_mock, send_mock, _, _, _ = self._run_handler(
            user_content="今天真的有点难受",
            user_emotion={"sadness": 0.9},
            chat_side_effect=[RuntimeError("boom"), RuntimeError("boom again")],
        )

        self.assertEqual(chat_mock.await_count, 2)
        fallback_message = send_mock.await_args.args[1]
        self.assertEqual(fallback_message, "我在呢[抱抱]，你继续说，我认真听着。")
        self.assertNotIn("网络", fallback_message)
        self.assertNotIn("卡住", fallback_message)
        self.assertNotIn("系统", fallback_message)
        self.assertNotIn("忙", fallback_message)

    def test_handler_uses_romantic_fallback_for_empty_response(self):
        _, _, send_mock, _, _, _ = self._run_handler(
            user_content="想你了",
            user_emotion={"love": 0.9},
            chat_side_effect=[""],
        )

        self.assertEqual(send_mock.await_args.args[1], "我在呀[心]，你再多和我说一点。")

    def test_handler_uses_persona_response_preferences_for_generation_limits(self):
        _, chat_mock, _, _, _, _ = self._run_handler(
            user_content="今天真的有点累啊",
            user_emotion={"tired": 0.8},
            chat_side_effect=["先抱一下你，慢慢和我说。"],
            persona_config={
                "display_name": "小甜",
                "response_preferences": {
                    "ultra_short_max_chars": 36,
                    "short_max_chars": 120,
                    "medium_max_chars": 150,
                    "long_max_chars": 180,
                },
            },
        )

        self.assertEqual(chat_mock.await_args.kwargs["max_tokens"], 192)

    def test_handler_includes_web_search_context_when_triggered(self):
        chat_mock = AsyncMock(return_value="AlphaFold 是做蛋白质结构预测的，我刚帮你查了下。")
        send_mock = AsyncMock(return_value={"errcode": 0})
        save_mock = AsyncMock(return_value=456)
        schedule_mock = patch.object(wecom.memory_service, "schedule_memory_processing")

        with (
            patch.object(wecom.wecom_service, "decrypt_message", return_value="<xml />"),
            patch.object(
                wecom.wecom_service,
                "parse_message",
                return_value={
                    "msg_type": "text",
                    "from_user": "user-1",
                    "content": "AlphaFold 是什么",
                },
            ),
            patch.object(wecom.wecom_service, "send_text_message", send_mock),
            patch.object(wecom.memory_service, "get_or_create_user", AsyncMock(return_value={"id": 1})),
            patch.object(wecom.memory_service, "get_conversation_context", AsyncMock(return_value={"today_chat_count": 1})),
            patch.object(wecom.memory_service, "get_recent_messages", AsyncMock(return_value=[])),
            patch.object(wecom.memory_service, "get_recent_agent_replies", AsyncMock(return_value=[])),
            patch.object(wecom.memory_service, "get_user_memory", AsyncMock(return_value=None)) as get_memory_mock,
            patch.object(wecom.memory_service, "save_conversation", save_mock),
            schedule_mock as mocked_schedule,
            patch.object(wecom.glm_service, "analyze_emotion", AsyncMock(return_value={"neutral": 1.0})),
            patch.object(
                wecom.glm_service,
                "maybe_collect_web_context",
                AsyncMock(
                    return_value={
                        "triggered": True,
                        "query": "AlphaFold 是什么",
                        "results": [
                            {
                                "title": "AlphaFold - DeepMind",
                                "media": "DeepMind",
                                "publish_date": "2024-01-01",
                                "content": "AlphaFold 是一个蛋白质结构预测系统。",
                                "link": "https://example.com/alphafold",
                            }
                        ],
                    }
                ),
            ),
            patch.object(wecom.glm_service, "chat_with_context", chat_mock),
            patch.object(wecom.emotion_engine, "update_state", AsyncMock(return_value={"current_mood": "happy", "intensity": 40})),
            patch.object(wecom.persona_service, "get_persona_config", return_value={"response_preferences": {}}),
        ):
            response = asyncio.run(
                wecom.wecom_callback_handler(
                    request=DummyRequest(),
                    msg_signature="sig",
                    timestamp="123",
                    nonce="nonce",
                )
            )

        self.assertEqual(response.status_code, 200)
        system_prompt = chat_mock.await_args.kwargs["system_prompt"]
        self.assertIn("Web Search Context", system_prompt)
        self.assertIn("AlphaFold - DeepMind", system_prompt)
        get_memory_mock.assert_awaited_once_with("wecom", "user-1", query_text="AlphaFold 是什么")
        mocked_schedule.assert_called_once()
        self.assertEqual(mocked_schedule.call_args.kwargs["conversation_id"], 456)


if __name__ == "__main__":
    unittest.main()
