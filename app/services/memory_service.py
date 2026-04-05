"""
记忆服务
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json

from app.models.user import User, Conversation, EmotionState, ShortTermMemory
from app.models.database import SessionLocal
from app.config import settings
from app.utils.helpers import summarize_recent_agent_replies


class MemoryService:
    """记忆管理服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.max_short_term_messages = settings.max_short_term_messages

    async def get_or_create_user(self, wecom_user_id: str) -> Dict:
        """
        获取或创建用户

        Args:
            wecom_user_id: 企业微信用户 ID

        Returns:
            用户信息
        """
        # 查询用户
        user = self.db.query(User).filter(User.wecom_user_id == wecom_user_id).first()

        if not user:
            # 创建新用户
            user = User(
                wecom_user_id=wecom_user_id,
                profile=self._get_default_profile(),
                basic_info={},
                emotional_patterns={},
                relationship_milestones=[],
                preferences=self._get_default_preferences(),
                first_interaction=datetime.now(),
                last_interaction=datetime.now(),
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        # 更新最后互动时间
        user.last_interaction = datetime.now()
        user.total_conversations += 1
        self.db.commit()

        return {
            "id": user.id,
            "wecom_user_id": user.wecom_user_id,
            "profile": user.profile,
            "preferences": user.preferences,
            "first_interaction": user.first_interaction,
            "relationship_days": (datetime.now() - user.first_interaction).days,
        }

    def _get_default_profile(self) -> Dict:
        """获取默认用户画像"""
        return {
            "basic_info": {
                "work_type": "",
                "hobbies": [],
                "daily_routine": "",
                "stress_triggers": [],
            },
            "emotional_patterns": {
                "happy_topics": [],
                "stress_topics": [],
                "comfort_needs": ["倾听", "鼓励", "陪伴"],
            },
            "relationship_milestones": [],
            "preferences": {
                "chat_style": "温柔但有趣",
                "love_language": "quality_time",
                "topics_to_avoid": [],
                "favorite_memories": [],
            },
        }

    def _get_default_preferences(self) -> Dict:
        """获取默认偏好"""
        return {
            "chat_style": "温柔但有趣",
            "love_language": "quality_time",
            "topics_to_avoid": [],
            "favorite_memories": [],
        }

    async def get_conversation_context(self, user_id: str) -> Dict:
        """
        获取对话上下文

        Args:
            user_id: 用户 ID（企业微信用户 ID）

        Returns:
            对话上下文
        """
        # 查询用户
        user = self.db.query(User).filter(User.wecom_user_id == user_id).first()
        if not user:
            return {}

        # 获取最近对话
        recent_conversations = (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(5)
            .all()
        )

        # 构建上下文
        context = {
            "recent_messages": [],
            "today_chat_count": 0,
            "user_mood_today": None,
            "last_chat_time": None,
        }

        today = datetime.now().date()
        for conv in recent_conversations:
            if conv.created_at.date() == today:
                context["today_chat_count"] += 1

            context["recent_messages"].append({
                "user": conv.user_message,
                "agent": conv.agent_message,
                "time": conv.created_at.strftime("%H:%M"),
            })

            if context["last_chat_time"] is None:
                context["last_chat_time"] = conv.created_at

        return context

    async def get_recent_messages(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取最近的对话消息

        Args:
            user_id: 用户 ID（企业微信用户 ID）
            limit: 返回的消息数量

        Returns:
            消息列表（格式化为 LLM 输入格式）
        """
        user = self.db.query(User).filter(User.wecom_user_id == user_id).first()
        if not user:
            return []

        conversations = (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .all()
        )

        # 反转顺序，使最早的对话在前
        conversations = list(reversed(conversations))

        messages = []
        for conv in conversations:
            messages.append({"role": "user", "content": conv.user_message})
            messages.append({"role": "assistant", "content": conv.agent_message})

        return messages

    async def get_recent_agent_replies(self, user_id: str, limit: int = 3) -> List[str]:
        """获取最近几条有意义的 Agent 回复摘要。"""
        user = self.db.query(User).filter(User.wecom_user_id == user_id).first()
        if not user:
            return []

        conversations = (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(max(limit * 2, limit))
            .all()
        )

        replies = [conv.agent_message for conv in conversations if conv.agent_message]
        return summarize_recent_agent_replies(replies, limit=limit)

    async def save_conversation(
        self,
        user_id: str,
        user_message: str,
        agent_message: str,
        user_emotion: Dict,
        agent_emotion: Dict,
    ) -> None:
        """
        保存对话记录

        Args:
            user_id: 用户 ID（企业微信用户 ID）
            user_message: 用户消息
            agent_message: Agent 回复
            user_emotion: 用户情绪分析结果
            agent_emotion: Agent 情绪状态
        """
        user = self.db.query(User).filter(User.wecom_user_id == user_id).first()
        if not user:
            return

        # 确定主要情绪
        user_mood = max(user_emotion.keys(), key=lambda k: user_emotion.get(k, 0))
        agent_mood = agent_emotion.get("current_mood", "happy")
        agent_intensity = agent_emotion.get("intensity", 0)

        conversation = Conversation(
            user_id=user.id,
            user_message=user_message,
            agent_message=agent_message,
            user_emotion=user_mood,
            agent_emotion=agent_mood,
            agent_emotion_intensity=agent_intensity,
            context_used=True,
        )
        self.db.add(conversation)
        self.db.commit()

    async def update_user_profile(self, user_id: str, profile_update: Dict) -> None:
        """
        更新用户画像

        Args:
            user_id: 用户 ID（企业微信用户 ID）
            profile_update: 要更新的画像字段
        """
        user = self.db.query(User).filter(User.wecom_user_id == user_id).first()
        if not user:
            return

        # 合并更新
        current_profile = user.profile or {}
        for key, value in profile_update.items():
            current_profile[key] = value

        user.profile = current_profile
        self.db.commit()


# 全局记忆服务实例
memory_service = MemoryService()
