"""
数据库基础配置和模型定义
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, declared_attr

Base = declarative_base()


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wecom_user_id = Column(String(64), unique=True, nullable=False, comment="企业微信用户ID")
    nickname = Column(String(100), comment="用户昵称")
    avatar_url = Column(String(255), comment="头像URL")

    # 用户画像
    profile = Column(JSON, comment="用户画像JSON")
    # 基础信息
    basic_info = Column(JSON, comment="基础信息JSON")
    # 情感模式
    emotional_patterns = Column(JSON, comment="情感模式JSON")
    # 关系里程碑
    relationship_milestones = Column(JSON, comment="关系里程碑JSON")
    # 偏好
    preferences = Column(JSON, comment="用户偏好JSON")

    # 统计信息
    total_conversations = Column(Integer, default=0, comment="总对话次数")
    first_interaction = Column(DateTime, comment="首次互动时间")
    last_interaction = Column(DateTime, comment="最后互动时间")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    conversations = relationship("Conversation", back_populates="user")
    emotion_states = relationship("EmotionState", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, wecom_user_id={self.wecom_user_id})>"


class Conversation(Base):
    """对话模型"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_conversation_user"), nullable=False, comment="用户ID")
    session_id = Column(String(64), comment="会话ID")

    # 消息内容
    user_message = Column(Text, comment="用户消息")
    agent_message = Column(Text, comment="Agent回复")

    # 消息元数据
    user_emotion = Column(String(32), comment="检测到的用户情绪")
    agent_emotion = Column(String(32), comment="Agent情绪状态")
    agent_emotion_intensity = Column(Integer, default=0, comment="Agent情绪强度")

    # 上下文信息
    context_used = Column(Boolean, default=False, comment="是否使用了上下文")
    memories_used = Column(JSON, comment="使用的记忆列表")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"


class EmotionState(Base):
    """情绪状态模型"""

    __tablename__ = "emotion_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_emotion_state_user"), nullable=False, comment="用户ID")

    # 情绪状态
    current_mood = Column(String(32), default="happy", comment="当前情绪")
    intensity = Column(Integer, default=0, comment="情绪强度(0-100)")

    # 各情绪状态强度
    happy_intensity = Column(Integer, default=0, comment="开心强度")
    caring_intensity = Column(Integer, default=0, comment="关心强度")
    playful_intensity = Column(Integer, default=0, comment="俏皮强度")
    jealous_intensity = Column(Integer, default=0, comment="吃醋强度")
    worried_intensity = Column(Integer, default=0, comment="担心强度")
    romantic_intensity = Column(Integer, default=0, comment="浪漫强度")
    upset_intensity = Column(Integer, default=0, comment="小情绪强度")
    missing_intensity = Column(Integer, default=0, comment="思念强度")

    # 情绪历史（最近几次变化）
    emotion_history = Column(JSON, comment="情绪历史记录")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    user = relationship("User", back_populates="emotion_states")

    def __repr__(self):
        return f"<EmotionState(id={self.id}, mood={self.current_mood}, intensity={self.intensity})>"


class ShortTermMemory(Base):
    """短期记忆模型"""

    __tablename__ = "short_term_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_short_term_memory_user"), nullable=False, comment="用户ID")
    session_id = Column(String(64), comment="会话ID")

    # 对话上下文
    messages = Column(JSON, comment="对话消息列表")
    conversation_summary = Column(Text, comment="对话摘要")
    pending_topics = Column(JSON, comment="未完成话题")
    emotion_trend = Column(String(32), comment="情感趋势")

    # 今日记忆
    today_chat_count = Column(Integer, default=0, comment="今日对话次数")
    user_mood_today = Column(String(32), comment="用户今日心情")
    user_worries = Column(JSON, comment="用户提到的烦恼")
    user_joys = Column(JSON, comment="用户分享的快乐")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<ShortTermMemory(id={self.id}, user_id={self.user_id})>"