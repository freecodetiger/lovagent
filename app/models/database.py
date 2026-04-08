"""
数据库初始化
"""

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
import app.models.admin  # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.emotion  # noqa: F401
from app.models.user import Base

logger = logging.getLogger(__name__)


# 创建数据库引擎
if settings.database_type == "sqlite":
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=False,  # 设为 True 可以看到 SQL 语句
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,  # 设为 True 可以看到 SQL 语句
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    _run_compat_migrations()
    logger.info("数据库表创建完成")


def _run_compat_migrations() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        _ensure_users_channel_columns(inspector, conn)
        _ensure_proactive_channel_columns(inspector, conn)


def _ensure_users_channel_columns(inspector, conn) -> None:
    tables = inspector.get_table_names()
    if "users" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("users")}
    if "channel" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN channel VARCHAR(32) DEFAULT 'wecom' NOT NULL"))
    has_legacy_wecom_id = "wecom_user_id" in columns
    if "external_user_id" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN external_user_id VARCHAR(128)"))
        if has_legacy_wecom_id:
            conn.execute(text("UPDATE users SET external_user_id = wecom_user_id WHERE external_user_id IS NULL"))
    conn.execute(text("UPDATE users SET channel = 'wecom' WHERE channel IS NULL OR channel = ''"))
    if has_legacy_wecom_id:
        conn.execute(
            text("UPDATE users SET external_user_id = wecom_user_id WHERE external_user_id IS NULL OR external_user_id = ''")
        )


def _ensure_proactive_channel_columns(inspector, conn) -> None:
    tables = inspector.get_table_names()
    if "proactive_chat_configs" in tables:
        columns = {item["name"] for item in inspector.get_columns("proactive_chat_configs")}
        has_legacy_target = "target_wecom_user_id" in columns
        if "target_channel" not in columns:
            conn.execute(text("ALTER TABLE proactive_chat_configs ADD COLUMN target_channel VARCHAR(32) DEFAULT 'wecom' NOT NULL"))
        if "target_external_user_id" not in columns:
            conn.execute(text("ALTER TABLE proactive_chat_configs ADD COLUMN target_external_user_id VARCHAR(128)"))
            if has_legacy_target:
                conn.execute(
                    text(
                        "UPDATE proactive_chat_configs "
                        "SET target_external_user_id = target_wecom_user_id "
                        "WHERE target_external_user_id IS NULL"
                    )
                )
        conn.execute(text("UPDATE proactive_chat_configs SET target_channel = 'wecom' WHERE target_channel IS NULL OR target_channel = ''"))

    if "proactive_chat_logs" in tables:
        columns = {item["name"] for item in inspector.get_columns("proactive_chat_logs")}
        has_legacy_target = "target_wecom_user_id" in columns
        if "target_channel" not in columns:
            conn.execute(text("ALTER TABLE proactive_chat_logs ADD COLUMN target_channel VARCHAR(32) DEFAULT 'wecom' NOT NULL"))
        if "target_external_user_id" not in columns:
            conn.execute(text("ALTER TABLE proactive_chat_logs ADD COLUMN target_external_user_id VARCHAR(128)"))
            if has_legacy_target:
                conn.execute(
                    text(
                        "UPDATE proactive_chat_logs "
                        "SET target_external_user_id = target_wecom_user_id "
                        "WHERE target_external_user_id IS NULL"
                    )
                )
        conn.execute(text("UPDATE proactive_chat_logs SET target_channel = 'wecom' WHERE target_channel IS NULL OR target_channel = ''"))


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
