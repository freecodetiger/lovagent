"""
企业微信消息服务
"""

import xml.etree.ElementTree as ET
from wechatpy.enterprise import WeChatClient
from wechatpy.enterprise.crypto import WeChatCrypto

from app.config import settings


class WeComService:
    """企业微信服务"""

    def __init__(self):
        self.corp_id = settings.wecom_corp_id
        self.agent_id = settings.wecom_agent_id
        self.secret = settings.wecom_secret
        self.token = settings.wecom_token
        self.encoding_aes_key = settings.wecom_encoding_aes_key

        # 企业微信加解密工具
        self.crypto = WeChatCrypto(self.token, self.encoding_aes_key, self.corp_id)

        # 企业微信客户端
        self.client = WeChatClient(
            self.corp_id,
            self.secret,
        )

    def verify_callback(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """校验企业微信回调并返回解密后的明文 echostr"""
        return self.crypto.check_signature(msg_signature, timestamp, nonce, echostr)

    def decrypt_message(self, encrypted_xml: str, msg_signature: str, timestamp: str, nonce: str) -> str:
        """解密消息"""
        return self.crypto.decrypt_message(encrypted_xml, msg_signature, timestamp, nonce)

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
        return f"""<xml>
<ToUserName>{to_user}</ToUserName>
<FromUserName>{self.agent_id}</FromUserName>
<CreateTime>{int(float(0))}</CreateTime>
<MsgType>text</MsgType>
<Content>{content}</Content>
</xml>"""

    async def send_text_message(self, to_user: str, content: str) -> dict:
        """发送文本消息"""
        return self.client.message.send_text(
            int(self.agent_id),
            to_user,
            content,
        )

    async def send_markdown_message(self, to_user: str, content: str) -> dict:
        """发送 Markdown 消息"""
        return self.client.message.send(
            int(self.agent_id),
            to_user,
            msg={
                "msgtype": "markdown",
                "markdown": {"content": content},
            },
        )

    def get_access_token(self) -> str:
        """获取 access_token"""
        return self.client.access_token


# 全局服务实例
wecom_service = WeComService()
