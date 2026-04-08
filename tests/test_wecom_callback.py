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
    def test_handler_registers_event_and_schedules_processing(self):
        with (
            patch.object(wecom.wecom_service, "decrypt_message", return_value="<xml />"),
            patch.object(
                wecom.wecom_service,
                "parse_message",
                return_value={
                    "msg_id": "msg-1",
                    "msg_type": "text",
                    "from_user": "user-1",
                    "content": "今天有点累",
                },
            ),
            patch.object(
                wecom.incoming_aggregation_service,
                "register_event",
                AsyncMock(return_value={"duplicate": False, "batch_id": 101, "user_id": "user-1"}),
            ) as register_mock,
            patch.object(wecom.incoming_aggregation_service, "schedule_user_processing") as schedule_mock,
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
        self.assertEqual(response.body.decode(), "success")
        register_mock.assert_awaited_once()
        schedule_mock.assert_called_once_with("user-1")

    def test_handler_skips_scheduling_for_duplicate_event(self):
        with (
            patch.object(wecom.wecom_service, "decrypt_message", return_value="<xml />"),
            patch.object(
                wecom.wecom_service,
                "parse_message",
                return_value={
                    "msg_id": "msg-1",
                    "msg_type": "text",
                    "from_user": "user-1",
                    "content": "今天有点累",
                },
            ),
            patch.object(
                wecom.incoming_aggregation_service,
                "register_event",
                AsyncMock(return_value={"duplicate": True, "batch_id": 101, "user_id": "user-1"}),
            ) as register_mock,
            patch.object(wecom.incoming_aggregation_service, "schedule_user_processing") as schedule_mock,
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
        self.assertEqual(response.body.decode(), "success")
        register_mock.assert_awaited_once()
        schedule_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
