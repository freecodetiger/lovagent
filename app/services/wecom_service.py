"""
企业微信消息服务
"""

import xml.etree.ElementTree as ET
from wechatpy.enterprise import WeChatClient
from wechatpy.enterprise.crypto import WeChatCrypto

from app.services.runtime_config_service import runtime_config_service


class WeComService:
    """企业微信服务"""

    def __init__(self):
        pass

    def _current_config(self) -> dict:
        return runtime_config_service.get_effective_wecom_config()

    def _build_crypto(self) -> WeChatCrypto:
        config = self._current_config()
        return WeChatCrypto(config["token"], config["encoding_aes_key"], config["corp_id"])

    def _build_client(self) -> WeChatClient:
        config = self._current_config()
        return WeChatClient(config["corp_id"], config["secret"])

    def verify_callback(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """校验企业微信回调并返回解密后的明文 echostr"""
        return self._build_crypto().check_signature(msg_signature, timestamp, nonce, echostr)

    def decrypt_message(self, encrypted_xml: str, msg_signature: str, timestamp: str, nonce: str) -> str:
        """解密消息"""
        return self._build_crypto().decrypt_message(encrypted_xml, msg_signature, timestamp, nonce)

    def parse_message(self, xml_content: str) -> dict:
        """解析 XML 消息"""
        root = ET.fromstring(xml_content)

        message = {
            "to_user": root.find("ToUserName").text,
            "from_user": root.find("FromUserName").text,
            "create_time": root.find("CreateTime").text,
            "msg_type": root.find("MsgType").text,
            "msg_id": root.find("MsgId").text,
            "agent_id": root.find("AgentID").text,
        }

        # 根据消息类型解析内容
        msg_type = message["msg_type"]
        if msg_type == "text":
            message["content"] = root.find("Content").text
        elif msg_type == "image":
            message["image_url"] = root.find("ImageUrl").text if root.find("ImageUrl") is not None else None
            message["media_id"] = root.find("MediaId").text if root.find("MediaId") is not None else None
        elif msg_type == "voice":
            message["media_id"] = root.find("MediaId").text if root.find("MediaId") is not None else None
            message["format"] = root.find("Format").text if root.find("Format") is not None else None
        elif msg_type == "video":
            message["media_id"] = root.find("MediaId").text if root.find("MediaId") is not None else None
            message["thumb_media_id"] = root.find("ThumbMediaId").text if root.find("ThumbMediaId") is not None else None
        elif msg_type == "location":
            message["location_x"] = root.find("Location_X").text
            message["location_y"] = root.find("Location_Y").text
            message["label"] = root.find("Label").text if root.find("Label") is not None else None

        return message

    def build_text_message(self, to_user: str, content: str) -> str:
        """构建文本消息 XML"""
        config = self._current_config()
        return f"""<xml>
<ToUserName>{to_user}</ToUserName>
<FromUserName>{config["agent_id"]}</FromUserName>
<CreateTime>{int(float(0))}</CreateTime>
<MsgType>text</MsgType>
<Content>{content}</Content>
</xml>"""

    async def send_text_message(self, to_user: str, content: str) -> dict:
        """发送文本消息"""
        config = self._current_config()
        client = self._build_client()
        return client.message.send_text(
            int(config["agent_id"]),
            to_user,
            content,
        )

    async def send_markdown_message(self, to_user: str, content: str) -> dict:
        """发送 Markdown 消息"""
        config = self._current_config()
        client = self._build_client()
        return client.message.send(
            int(config["agent_id"]),
            to_user,
            msg={
                "msgtype": "markdown",
                "markdown": {"content": content},
            },
        )

    def get_access_token(self) -> str:
        """获取 access_token"""
        return self._build_client().access_token


# 全局服务实例
wecom_service = WeComService()
