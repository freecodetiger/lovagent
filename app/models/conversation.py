"""
对话相关模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from app.models.user import Base


class Message(Base):
    """消息模型"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), comment="对话ID")

    role = Column(String(16), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")

    # 消息元数据
    emotion = Column(String(32), comment="情绪")
    timestamp = Column(DateTime, default=datetime.now, comment="时间戳")

    # 分析信息
    keywords = Column(JSON, comment="关键词列表")
    sentiment_score = Column(Integer, comment="情感分数(-100到100)")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"


class ConversationSession(Base):
    """会话模型"""

    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    session_id = Column(String(64), unique=True, nullable=False, comment="会话ID")

    # 会话状态
    status = Column(String(16), default="active", comment="状态: active/ended")

    # 会话统计
    message_count = Column(Integer, default=0, comment="消息数量")
    avg_sentiment = Column(Integer, comment="平均情感分数")

    # 会话时间
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    ended_at = Column(DateTime, comment="结束时间")
    last_message_at = Column(DateTime, comment="最后消息时间")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<ConversationSession(id={self.id}, session_id={self.session_id})>"