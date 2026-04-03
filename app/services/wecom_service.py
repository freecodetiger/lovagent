"""
企业微信消息服务
"""

import base64
import struct
import xml.etree.ElementTree as ET
from typing import Optional
from Crypto.Cipher import AES
from wechatpy.enterprise import WeChatClient
from wechatpy.exceptions import InvalidSignatureException

from app.config import settings


class WeComService:
    """企业微信服务"""

    def __init__(self):
        self.corp_id = settings.wecom_corp_id
        self.agent_id = settings.wecom_agent_id
        self.secret = settings.wecom_secret
        self.token = settings.wecom_token
        self.encoding_aes_key = settings.wecom_encoding_aes_key

        # 企业微信客户端
        self.client = WeChatClient(
            self.corp_id,
            self.secret,
        )

    def decrypt_echostr(self, echostr: str) -> str:
        """解密验证请求的 echostr"""
        # EncodingAESKey 是 43 字符，需要补 '=' 到 44 字符
        aes_key = base64.b64decode(self.encoding_aes_key + '=')

        # Base64 解码 echostr
        encrypted_data = base64.b64decode(echostr)

        # AES-256-CBC 解密，IV 是 aes_key 的前 16 字节
        cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
        decrypted = cipher.decrypt(encrypted_data)

        # 去除 PKCS7 padding
        pad = decrypted[-1]
        decrypted = decrypted[:-pad]

        # 格式: 随机字符串(16字节) + msg_len(4字节网络序) + msg_content + corp_id
        msg_len = struct.unpack('>I', decrypted[16:20])[0]
        msg_content = decrypted[20:20 + msg_len].decode('utf-8')
        from_corp_id = decrypted[20 + msg_len:].decode('utf-8')

        # 验证 corp_id
        if from_corp_id != self.corp_id:
            raise ValueError(f'CorpID 不匹配: {from_corp_id} != {self.corp_id}')

        return msg_content

    def decrypt_message(self, encrypted_xml: str, msg_signature: str, timestamp: str, nonce: str) -> str:
        """解密消息"""
        # 使用相同的方式解密
        aes_key = base64.b64decode(self.encoding_aes_key + '=')

        # 解析 XML 获取 Encrypt 字段
        root = ET.fromstring(encrypted_xml)
        encrypt = root.find('Encrypt').text

        # Base64 解码
        encrypted_data = base64.b64decode(encrypt)

        # AES 解密
        cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
        decrypted = cipher.decrypt(encrypted_data)

        # 去除 PKCS7 padding
        pad = decrypted[-1]
        decrypted = decrypted[:-pad]

        # 解析内容
        msg_len = struct.unpack('>I', decrypted[16:20])[0]
        msg_content = decrypted[20:20 + msg_len].decode('utf-8')
        from_corp_id = decrypted[20 + msg_len:].decode('utf-8')

        return msg_content

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
        return self.client.message.send(
            self.agent_id,
            to_user,
            "text",
            {"content": content},
        )

    async def send_markdown_message(self, to_user: str, content: str) -> dict:
        """发送 Markdown 消息"""
        return self.client.message.send(
            self.agent_id,
            to_user,
            "markdown",
            {"content": content},
        )

    def get_access_token(self) -> str:
        """获取 access_token"""
        return self.client.access_token


# 全局服务实例
wecom_service = WeComService()