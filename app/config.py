"""
配置管理模块
"""

import os
from hashlib import sha256
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
    zhipu_thinking_type: str = os.getenv("ZHIPU_THINKING_TYPE", "disabled")
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_web_search_enabled: bool = os.getenv("ZHIPU_WEB_SEARCH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    zhipu_web_search_engine: str = os.getenv("ZHIPU_WEB_SEARCH_ENGINE", "search_std")
    zhipu_web_search_count: int = int(os.getenv("ZHIPU_WEB_SEARCH_COUNT", "4"))
    zhipu_web_search_content_size: str = os.getenv("ZHIPU_WEB_SEARCH_CONTENT_SIZE", "medium")
    model_provider: str = os.getenv("MODEL_PROVIDER", "glm")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # 数据库配置
    database_type: str = os.getenv("DATABASE_TYPE", "sqlite")
    database_path: str = os.getenv("DATABASE_PATH", "./girlchat.db")

    # MySQL 配置 (保留用于生产环境)
    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "girlchat")

    # 服务配置
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "")
    proactive_scheduler_interval_seconds: int = int(os.getenv("PROACTIVE_SCHEDULER_INTERVAL_SECONDS", "60"))
    admin_dev_origins_raw: str = os.getenv(
        "ADMIN_DEV_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    admin_password: str = os.getenv("ADMIN_PASSWORD", "lovagent-admin")
    admin_cookie_name: str = os.getenv("ADMIN_COOKIE_NAME", "lovagent_admin_session")
    admin_session_secret: str = os.getenv("ADMIN_SESSION_SECRET", "")

    # 记忆配置
    max_short_term_messages: int = 20  # 短期记忆保留的最大消息数
    max_context_length: int = 4000  # 最大上下文长度（字符）

    @property
    def database_url(self) -> str:
        """生成数据库连接 URL"""
        if self.database_type == "sqlite":
            return f"sqlite:///{self.database_path}"
        else:
            return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    @property
    def mysql_url(self) -> str:
        """生成 MySQL 连接 URL (保留兼容性)"""
        return self.database_url

    @property
    def wecom_callback_url(self) -> str:
        """生成企业微信回调地址"""
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/wecom/callback"
        return f"http://{self.server_host}:{self.server_port}/wecom/callback"

    @property
    def resolved_admin_session_secret(self) -> str:
        """获取管理后台 Session 密钥。"""
        if self.admin_session_secret:
            return self.admin_session_secret

        raw = f"{self.admin_password}:{self.wecom_token}:{self.wecom_corp_id}"
        return sha256(raw.encode("utf-8")).hexdigest()

    @property
    def admin_dev_origins(self) -> list[str]:
        """前端本地开发允许的来源。"""
        values = [item.strip() for item in self.admin_dev_origins_raw.split(",")]
        return [item for item in values if item]


# 全局配置实例
settings = Settings()
