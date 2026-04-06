"""
数据库初始化
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
import app.models.admin  # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.emotion  # noqa: F401
from app.models.user import Base


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
    print("✅ 数据库表创建完成")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
