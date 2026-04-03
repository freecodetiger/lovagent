"""
情绪状态模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from app.models.user import Base


class EmotionTrigger(Base):
    """情绪触发记录"""

    __tablename__ = "emotion_triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emotion_state_id = Column(Integer, ForeignKey("emotion_states.id"), comment="情绪状态ID")

    trigger_type = Column(String(32), comment="触发类型")
    trigger_content = Column(String(255), comment="触发内容")
    emotion_before = Column(String(32), comment="触发前情绪")
    emotion_after = Column(String(32), comment="触发后情绪")
    intensity_change = Column(Integer, comment="强度变化")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<EmotionTrigger(id={self.id}, trigger_type={self.trigger_type})>"


class EmotionHistory(Base):
    """情绪历史记录"""

    __tablename__ = "emotion_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")

    date = Column(DateTime, nullable=False, comment="日期")

    # 当日情绪统计
    dominant_emotion = Column(String(32), comment="主导情绪")
    emotion_counts = Column(JSON, comment="各情绪出现次数统计")
    avg_intensity = Column(Integer, comment="平均强度")

    # 情感趋势
    positive_ratio = Column(Integer, comment="正面情绪比例")
    negative_ratio = Column(Integer, comment="负面情绪比例")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<EmotionHistory(id={self.id}, date={self.date})>"