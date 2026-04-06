"""
管理后台相关模型
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text

from app.models.user import Base


class AgentConfig(Base):
    """全局 Agent 配置。"""

    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, nullable=False, comment="配置键")
    display_name = Column(String(100), nullable=False, default="默认人设", comment="展示名称")

    persona_core = Column(JSON, nullable=False, default=dict, comment="基础人设核心配置")
    persona_text = Column(Text, comment="渲染后的基础人设文本")
    personality_metrics = Column(JSON, nullable=False, default=dict, comment="人格维度")
    topics_to_avoid = Column(JSON, nullable=False, default=list, comment="禁区话题")
    recommended_topics = Column(JSON, nullable=False, default=list, comment="推荐话题")
    response_rules = Column(JSON, nullable=False, default=list, comment="回复规则")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, config_key={self.config_key})>"


class ProactiveChatConfig(Base):
    """主动聊天配置。"""

    __tablename__ = "proactive_chat_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, nullable=False, comment="配置键")
    enabled = Column(Boolean, nullable=False, default=False, comment="是否启用主动聊天")
    target_wecom_user_id = Column(String(64), comment="目标企业微信用户 ID")
    scheduled_windows = Column(JSON, nullable=False, default=list, comment="固定时段窗口")
    inactivity_trigger_hours = Column(Integer, nullable=False, default=6, comment="多久未互动后主动发起")
    quiet_hours = Column(JSON, nullable=False, default=dict, comment="免打扰时段")
    max_messages_per_day = Column(Integer, nullable=False, default=4, comment="每天最多主动消息数")
    min_interval_minutes = Column(Integer, nullable=False, default=180, comment="两次主动消息的最小间隔")
    tone_hint = Column(Text, comment="主动聊天语气提示")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<ProactiveChatConfig(id={self.id}, config_key={self.config_key})>"


class ProactiveChatLog(Base):
    """主动聊天发送日志。"""

    __tablename__ = "proactive_chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_wecom_user_id = Column(String(64), nullable=False, comment="目标企业微信用户 ID")
    trigger_type = Column(String(32), nullable=False, comment="触发类型")
    window_key = Column(String(32), comment="固定窗口 key")
    content = Column(Text, comment="发送内容")
    status = Column(String(32), nullable=False, default="pending", comment="发送状态")
    error_message = Column(Text, comment="错误信息")
    sent_at = Column(DateTime, default=datetime.now, comment="发送时间")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<ProactiveChatLog(id={self.id}, target={self.target_wecom_user_id}, trigger={self.trigger_type})>"


class RuntimeConfig(Base):
    """运行时配置。"""

    __tablename__ = "runtime_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, nullable=False, comment="配置键")
    config_value = Column(JSON, nullable=False, default=dict, comment="运行时配置 JSON")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<RuntimeConfig(id={self.id}, config_key={self.config_key})>"
