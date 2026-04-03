"""
配置管理模块
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加载环境变量
load_dotenv()


class Settings(BaseSettings):
    """应用配置"""

    # 企业微信配置
    wecom_corp_id: str = os.getenv("WECOM_CORP_ID", "")
    wecom_agent_id: str = os.getenv("WECOM_AGENT_ID", "")
    wecom_secret: str = os.getenv("WECOM_SECRET", "")
    wecom_token: str = os.getenv("WECOM_TOKEN", "")
    wecom_encoding_aes_key: str = os.getenv("WECOM_ENCODING_AES_KEY", "")

    # 智谱 API 配置
    zhipu_api_key: str = os.getenv("ZHIPU_API_KEY", "")
    zhipu_model: str = os.getenv("ZHIPU_MODEL", "glm-5")
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # 数据库配置
    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "girlchat")

    # 服务配置
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))

    # 记忆配置
    max_short_term_messages: int = 20  # 短期记忆保留的最大消息数
    max_context_length: int = 4000  # 最大上下文长度（字符）

    @property
    def mysql_url(self) -> str:
        """生成 MySQL 连接 URL"""
        return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    @property
    def mysql_async_url(self) -> str:
        """生成异步 MySQL 连接 URL"""
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"


# 全局配置实例
settings = Settings()