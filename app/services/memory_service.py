"""
记忆服务
"""

import asyncio
from datetime import datetime
import logging
import re
from typing import Dict, Iterable, List, Optional

from app.config import settings
from app.models.database import SessionLocal
from app.models.user import Conversation, MemoryItem, ShortTermMemory, User
from app.utils.helpers import sanitize_input, summarize_recent_agent_replies

logger = logging.getLogger(__name__)


MEMORY_ITEM_SALIENCE = {
    "identity": 70,
    "preference": 72,
    "worry": 76,
    "milestone": 90,
    "taboo": 88,
    "todo_followup": 74,
}


class MemoryService:
    """记忆管理服务。"""

    def __init__(self):
        self.max_short_term_messages = settings.max_short_term_messages
        self._background_tasks: set[asyncio.Task] = set()
        self._user_locks: Dict[str, asyncio.Lock] = {}

    def _resolve_identity(self, channel: str, external_user_id: Optional[str] = None) -> tuple[str, str]:
        if external_user_id is None:
            return "wecom", channel
        return channel, external_user_id

    async def get_or_create_user(self, channel: str, external_user_id: Optional[str] = None) -> Dict:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                user = self._create_user(db, channel, external_user_id)

            user.last_interaction = datetime.now()
            user.total_conversations += 1
            db.commit()

            payload = self._build_profile_snapshot(user)
            payload["id"] = user.id
            payload["relationship_days"] = (datetime.now() - user.first_interaction).days
            return payload
        finally:
            db.close()

    async def get_conversation_context(self, channel: str, external_user_id: Optional[str] = None) -> Dict:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return {}

            recent_conversations = self._get_recent_conversations_rows(db, user.id, limit=5)
            short_term = self._get_or_create_short_term_memory(db, user.id)

            context = {
                "recent_messages": [],
                "today_chat_count": short_term.today_chat_count or 0,
                "user_mood_today": short_term.user_mood_today,
                "last_chat_time": None,
                "short_term_summary": short_term.conversation_summary or "",
                "pending_topics": list(short_term.pending_topics or []),
                "emotion_trend": short_term.emotion_trend or "",
            }

            for conversation in recent_conversations:
                context["recent_messages"].append(
                    {
                        "user": conversation.user_message,
                        "agent": conversation.agent_message,
                        "time": conversation.created_at.strftime("%H:%M"),
                    }
                )
                if context["last_chat_time"] is None:
                    context["last_chat_time"] = conversation.created_at

            if context["today_chat_count"] == 0:
                today = datetime.now().date()
                context["today_chat_count"] = sum(
                    1 for conversation in recent_conversations if conversation.created_at.date() == today
                )

            return context
        finally:
            db.close()

    async def get_recent_messages(self, channel: str, external_user_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return []

            conversations = self._get_recent_conversations_rows(db, user.id, limit=limit)
            conversations = list(reversed(conversations))

            messages: List[Dict] = []
            for conversation in conversations:
                if conversation.user_message:
                    messages.append({"role": "user", "content": conversation.user_message})
                if conversation.agent_message:
                    messages.append({"role": "assistant", "content": conversation.agent_message})
            return messages
        finally:
            db.close()

    async def get_recent_agent_replies(self, channel: str, external_user_id: Optional[str] = None, limit: int = 3) -> List[str]:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return []

            conversations = self._get_recent_conversations_rows(db, user.id, limit=max(limit * 2, limit))
            replies = [conversation.agent_message for conversation in conversations if conversation.agent_message]
            return summarize_recent_agent_replies(replies, limit=limit)
        finally:
            db.close()

    async def save_conversation(
        self,
        *,
        channel: Optional[str] = None,
        external_user_id: Optional[str] = None,
        user_message: str,
        agent_message: str,
        user_emotion: Dict,
        agent_emotion: Dict,
        memories_used: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> Optional[int]:
        if user_id and not external_user_id:
            channel, external_user_id = "wecom", user_id
        if not channel or not external_user_id:
            return None
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return None

            user_mood = max(user_emotion.keys(), key=lambda key: user_emotion.get(key, 0)) if user_emotion else "neutral"
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
                memories_used=memories_used or {"source": "reply"},
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation.id
        finally:
            db.close()

    async def update_user_profile(
        self,
        channel: str,
        external_user_id: Optional[str] = None,
        profile_update: Optional[Dict] = None,
    ) -> None:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        profile_update = profile_update or {}
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return

            current_profile = user.profile or {}
            for key, value in profile_update.items():
                current_profile[key] = value

            user.profile = current_profile
            db.commit()
        finally:
            db.close()

    async def list_users(self, query: str = "", limit: int = 20) -> List[Dict]:
        db = SessionLocal()
        try:
            user_query = db.query(User)
            cleaned_query = query.strip()
            if cleaned_query:
                like_value = f"%{cleaned_query}%"
                user_query = user_query.filter(
                    (User.external_user_id.ilike(like_value)) | (User.nickname.ilike(like_value))
                )

            users = (
                user_query
                .order_by(User.last_interaction.is_(None), User.last_interaction.desc(), User.created_at.desc())
                .limit(max(1, min(limit, 50)))
                .all()
            )

            return [
                {
                    "channel": user.channel,
                    "external_user_id": user.external_user_id,
                    "nickname": user.nickname or "",
                    "avatar_url": user.avatar_url or "",
                    "total_conversations": user.total_conversations,
                    "last_interaction": user.last_interaction.isoformat() if user.last_interaction else None,
                    "first_interaction": user.first_interaction.isoformat() if user.first_interaction else None,
                }
                for user in users
            ]
        finally:
            db.close()

    async def get_user_memory(self, channel: str, external_user_id: Optional[str] = None, query_text: str = "") -> Optional[Dict]:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return None

            short_term = self._get_or_create_short_term_memory(db, user.id)
            memory_items = self._select_relevant_memory_items(db, user.id, query_text=query_text, limit=6)
            payload = self._build_profile_snapshot(
                user,
                short_term_memory=self._serialize_short_term_memory(short_term),
                memory_items=[self._serialize_memory_item(item) for item in memory_items],
            )
            payload["recent_conversations"] = self._serialize_recent_conversations(
                self._get_recent_conversations_rows(db, user.id, limit=8)
            )
            return payload
        finally:
            db.close()

    async def upsert_user_memory(self, channel: str, external_user_id: Optional[str] = None, payload: Dict = None) -> Dict:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        payload = payload or {}
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                user = self._create_user(db, channel, external_user_id)

            user.nickname = str(payload.get("nickname") or "").strip() or None
            user.avatar_url = str(payload.get("avatar_url") or "").strip() or None
            user.basic_info = payload.get("basic_info") or {}
            user.emotional_patterns = payload.get("emotional_patterns") or {}
            user.relationship_milestones = payload.get("relationship_milestones") or []
            user.preferences = payload.get("preferences") or self._get_default_preferences()
            user.profile = {
                "basic_info": user.basic_info,
                "emotional_patterns": user.emotional_patterns,
                "relationship_milestones": user.relationship_milestones,
                "preferences": user.preferences,
            }
            db.commit()
        finally:
            db.close()

        memory = await self.get_user_memory(channel, external_user_id)
        return memory or self._empty_user_memory(channel, external_user_id)

    async def get_recent_conversations(self, channel: str, external_user_id: Optional[str] = None, limit: int = 8) -> List[Dict]:
        channel, external_user_id = self._resolve_identity(channel, external_user_id)
        db = SessionLocal()
        try:
            user = self._get_user_by_channel_external_id(db, channel, external_user_id)
            if not user:
                return []
            conversations = self._get_recent_conversations_rows(db, user.id, limit=limit)
            return self._serialize_recent_conversations(conversations)
        finally:
            db.close()

    def schedule_memory_processing(
        self,
        *,
        channel: str = "wecom",
        external_user_id: Optional[str] = None,
        conversation_id: Optional[int],
        user_message: str,
        agent_message: str,
        user_emotion: Dict,
        agent_emotion: Dict,
        wecom_user_id: Optional[str] = None,
    ) -> None:
        if wecom_user_id and not external_user_id:
            channel, external_user_id = "wecom", wecom_user_id
        else:
            channel, external_user_id = self._resolve_identity(channel, external_user_id)
        if not conversation_id:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        task = loop.create_task(
            self.process_memory_update(
                channel=channel,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                agent_message=agent_message,
                user_emotion=user_emotion,
                agent_emotion=agent_emotion,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)

    async def process_memory_update(
        self,
        *,
        channel: str = "wecom",
        external_user_id: Optional[str] = None,
        conversation_id: int,
        user_message: str,
        agent_message: str,
        user_emotion: Dict,
        agent_emotion: Dict,
        wecom_user_id: Optional[str] = None,
    ) -> None:
        if wecom_user_id and not external_user_id:
            channel, external_user_id = "wecom", wecom_user_id
        else:
            channel, external_user_id = self._resolve_identity(channel, external_user_id)
        user_key = self.build_user_key(channel, external_user_id)
        lock = self._user_locks.setdefault(user_key, asyncio.Lock())
        async with lock:
            from app.graph import run_memory_update_graph

            await run_memory_update_graph(
                {
                    "channel": channel,
                    "external_user_id": external_user_id,
                    "conversation_id": conversation_id,
                    "user_message": user_message,
                    "agent_message": agent_message,
                    "user_emotion": user_emotion,
                    "agent_emotion": agent_emotion,
                }
            )

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        self._background_tasks.discard(task)
        try:
            task.result()
        except Exception as exc:
            logger.exception("记忆异步提炼失败")

    def _get_user_by_channel_external_id(self, db, channel: str, external_user_id: str) -> Optional[User]:
        return (
            db.query(User)
            .filter(User.channel == channel, User.external_user_id == external_user_id)
            .first()
        )

    def _create_user(self, db, channel: str, external_user_id: str) -> User:
        user = User(
            channel=channel,
            external_user_id=external_user_id,
            profile=self._get_default_profile(),
            basic_info={},
            emotional_patterns={},
            relationship_milestones=[],
            preferences=self._get_default_preferences(),
            first_interaction=datetime.now(),
            last_interaction=datetime.now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def build_user_key(self, channel: str, external_user_id: str) -> str:
        return f"{channel}:{external_user_id}"

    def _get_or_create_short_term_memory(self, db, user_id: int) -> ShortTermMemory:
        memory = db.query(ShortTermMemory).filter(ShortTermMemory.user_id == user_id).first()
        if not memory:
            memory = ShortTermMemory(
                user_id=user_id,
                session_id=None,
                messages=[],
                conversation_summary="",
                pending_topics=[],
                emotion_trend="未知",
                today_chat_count=0,
                user_mood_today="neutral",
                user_worries=[],
                user_joys=[],
            )
            db.add(memory)
            db.commit()
            db.refresh(memory)

        self._reset_daily_short_term_memory_if_needed(memory)
        return memory

    def _reset_daily_short_term_memory_if_needed(self, memory: ShortTermMemory) -> None:
        updated_at = memory.updated_at or memory.created_at
        if updated_at and updated_at.date() == datetime.now().date():
            return

        memory.messages = []
        memory.conversation_summary = ""
        memory.pending_topics = []
        memory.today_chat_count = 0
        memory.user_mood_today = "neutral"
        memory.user_worries = []
        memory.user_joys = []
        memory.emotion_trend = "未知"

    def _get_recent_conversations_rows(self, db, user_id: int, limit: int = 8) -> List[Conversation]:
        return (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )

    def _serialize_recent_conversations(self, conversations: List[Conversation]) -> List[Dict]:
        return [
            {
                "id": conversation.id,
                "user_message": conversation.user_message,
                "agent_message": conversation.agent_message,
                "message_source": (conversation.memories_used or {}).get("source", "reply"),
                "user_emotion": conversation.user_emotion,
                "agent_emotion": conversation.agent_emotion,
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            }
            for conversation in conversations
        ]

    def _serialize_llm_messages(self, conversations: List[Conversation]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for conversation in reversed(conversations):
            if conversation.user_message:
                messages.append({"role": "user", "content": conversation.user_message})
            if conversation.agent_message:
                messages.append({"role": "assistant", "content": conversation.agent_message})
        return messages

    def _build_profile_snapshot(
        self,
        user: User,
        short_term_memory: Optional[Dict] = None,
        memory_items: Optional[List[Dict]] = None,
    ) -> Dict:
        profile = user.profile or self._get_default_profile()
        return {
            "channel": user.channel,
            "external_user_id": user.external_user_id,
            "nickname": user.nickname or "",
            "avatar_url": user.avatar_url or "",
            "profile": profile,
            "basic_info": user.basic_info or profile.get("basic_info", {}),
            "emotional_patterns": user.emotional_patterns or profile.get("emotional_patterns", {}),
            "relationship_milestones": user.relationship_milestones or profile.get("relationship_milestones", []),
            "preferences": user.preferences or profile.get("preferences", {}),
            "first_interaction": user.first_interaction,
            "last_interaction": user.last_interaction,
            "total_conversations": user.total_conversations,
            "short_term_memory": short_term_memory or {},
            "memory_items": memory_items or [],
        }

    def _serialize_short_term_memory(self, short_term: ShortTermMemory) -> Dict:
        return {
            "conversation_summary": short_term.conversation_summary or "",
            "pending_topics": list(short_term.pending_topics or []),
            "emotion_trend": short_term.emotion_trend or "",
            "today_chat_count": short_term.today_chat_count or 0,
            "user_mood_today": short_term.user_mood_today or "",
            "user_worries": list(short_term.user_worries or []),
            "user_joys": list(short_term.user_joys or []),
            "messages": list(short_term.messages or []),
        }

    def _serialize_memory_item(self, item: MemoryItem) -> Dict:
        return {
            "id": item.id,
            "content": item.content,
            "type": item.memory_type,
            "salience": item.salience,
            "confidence": item.confidence,
            "keywords": list(item.keywords or []),
            "entity_tags": list(item.entity_tags or []),
            "time_tags": list(item.time_tags or []),
            "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
            "source_conversation_id": item.source_conversation_id,
        }

    def _empty_user_memory(self, channel: str, external_user_id: str) -> Dict:
        return {
            "channel": channel,
            "external_user_id": external_user_id,
            "nickname": "",
            "avatar_url": "",
            "basic_info": {},
            "emotional_patterns": {},
            "relationship_milestones": [],
            "preferences": {},
            "recent_conversations": [],
            "short_term_memory": {},
            "memory_items": [],
        }

    def _get_default_profile(self) -> Dict:
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
        return {
            "chat_style": "温柔但有趣",
            "love_language": "quality_time",
            "topics_to_avoid": [],
            "favorite_memories": [],
            "likes": [],
            "dislikes": [],
        }

    def _should_use_llm_memory_extraction(self, user_message: str) -> bool:
        cleaned = sanitize_input(user_message)
        if len(cleaned) >= 10:
            return True

        markers = (
            "喜欢",
            "不喜欢",
            "讨厌",
            "工作",
            "加班",
            "压力",
            "焦虑",
            "第一",
            "纪念",
            "不想聊",
            "别提",
            "明天",
            "下周",
        )
        return any(marker in cleaned for marker in markers)

    def _rule_extract_memory(self, user_message: str, user_emotion: Dict) -> Dict[str, object]:
        cleaned = sanitize_input(user_message)
        result = self._empty_extraction_result()
        if not cleaned:
            return result

        identity_patterns = [
            (r"我是做([^，。！？\n]{1,16})的", "work_type"),
            (r"我是([^，。！？\n]{1,16})生", "work_type"),
            (r"我在([^，。！？\n]{1,16})工作", "work_type"),
            (r"我住在([^，。！？\n]{1,16})", "location"),
            (r"我在([^，。！？\n]{1,16})上班", "work_type"),
        ]
        for pattern, key in identity_patterns:
            match = re.search(pattern, cleaned)
            if match:
                value = match.group(1).strip()
                result["identity_facts"].append(
                    {"key": key, "value": value, "confidence": 0.92, "keywords": self._extract_query_terms(value)}
                )

        preference_matches = [
            (r"我喜欢([^，。！？\n]{1,20})", "likes"),
            (r"我爱([^，。！？\n]{1,20})", "likes"),
            (r"我不喜欢([^，。！？\n]{1,20})", "dislikes"),
            (r"我讨厌([^，。！？\n]{1,20})", "dislikes"),
        ]
        for pattern, key in preference_matches:
            for match in re.finditer(pattern, cleaned):
                value = match.group(1).strip()
                result["preferences"].append(
                    {"key": key, "value": value, "confidence": 0.88, "keywords": self._extract_query_terms(value)}
                )

        taboo_patterns = (
            r"别提([^，。！？\n]{1,20})",
            r"不要聊([^，。！？\n]{1,20})",
            r"不想聊([^，。！？\n]{1,20})",
        )
        for pattern in taboo_patterns:
            for match in re.finditer(pattern, cleaned):
                content = match.group(1).strip()
                result["taboos"].append(
                    {"content": content, "confidence": 0.9, "keywords": self._extract_query_terms(content)}
                )

        worry_markers = ("压力", "焦虑", "烦", "难受", "崩溃", "累", "加班", "失眠", "难过", "委屈")
        if any(marker in cleaned for marker in worry_markers):
            result["worries"].append(
                {"content": cleaned[:80], "confidence": 0.72, "keywords": self._extract_query_terms(cleaned)}
            )

        joy_markers = ("开心", "高兴", "太好了", "好耶", "想你", "爱你")
        if any(marker in cleaned for marker in joy_markers):
            result["user_joys"] = [cleaned[:40]]

        milestone_markers = ("第一次", "纪念日", "表白", "在一起", "想你了", "和好", "见面")
        if any(marker in cleaned for marker in milestone_markers):
            result["milestones"].append(
                {"content": cleaned[:80], "confidence": 0.68, "keywords": self._extract_query_terms(cleaned)}
            )

        followup_markers = ("明天", "今晚", "待会", "下周", "周末", "面试", "开会", "汇报", "考试", "出差")
        if any(marker in cleaned for marker in followup_markers):
            result["followups"].append(
                {"content": cleaned[:80], "confidence": 0.74, "keywords": self._extract_query_terms(cleaned)}
            )

        result["short_term_summary"] = cleaned[:80]
        result["emotion_trend"] = self._infer_emotion_trend(user_emotion)
        return result

    def _merge_extraction_results(self, *results: Dict[str, object], user_emotion: Optional[Dict] = None) -> Dict[str, object]:
        merged = self._empty_extraction_result()
        fact_buckets: Dict[str, Dict[str, Dict[str, object]]] = {
            "identity_facts": {},
            "preferences": {},
        }
        text_buckets: Dict[str, Dict[str, Dict[str, object]]] = {
            "worries": {},
            "milestones": {},
            "taboos": {},
            "followups": {},
        }

        for result in results:
            if not result:
                continue
            for name in ("identity_facts", "preferences"):
                for item in result.get(name, []):
                    if not isinstance(item, dict):
                        continue
                    bucket_key = f"{item.get('key', '').strip()}::{item.get('value', '').strip()}"
                    if "::" == bucket_key:
                        continue
                    fact_buckets[name][bucket_key] = item
            for name in ("worries", "milestones", "taboos", "followups"):
                for item in result.get(name, []):
                    if not isinstance(item, dict):
                        continue
                    content = str(item.get("content") or "").strip()
                    if not content:
                        continue
                    text_buckets[name][content] = item

            if result.get("short_term_summary"):
                merged["short_term_summary"] = str(result["short_term_summary"]).strip()[:120]
            if result.get("emotion_trend"):
                merged["emotion_trend"] = str(result["emotion_trend"]).strip()[:20]
            merged["user_joys"] = self._merge_string_lists(merged["user_joys"], result.get("user_joys") or [])

        merged["identity_facts"] = list(fact_buckets["identity_facts"].values())
        merged["preferences"] = list(fact_buckets["preferences"].values())
        for name in ("worries", "milestones", "taboos", "followups"):
            merged[name] = list(text_buckets[name].values())

        if not merged["emotion_trend"]:
            merged["emotion_trend"] = self._infer_emotion_trend(user_emotion or {})

        return merged

    def _empty_extraction_result(self) -> Dict[str, object]:
        return {
            "identity_facts": [],
            "preferences": [],
            "worries": [],
            "milestones": [],
            "taboos": [],
            "followups": [],
            "short_term_summary": "",
            "emotion_trend": "",
            "user_joys": [],
        }

    def _apply_long_term_updates(self, user: User, extracted: Dict[str, object]) -> None:
        basic_info = dict(user.basic_info or {})
        emotional_patterns = dict(user.emotional_patterns or {})
        preferences = dict(user.preferences or self._get_default_preferences())
        milestones = list(user.relationship_milestones or [])

        for item in extracted.get("identity_facts", []):
            key = str(item.get("key") or "").strip()
            value = str(item.get("value") or "").strip()
            if key and value:
                basic_info[key] = self._merge_scalar_value(basic_info.get(key), value)

        for item in extracted.get("preferences", []):
            key = str(item.get("key") or "").strip()
            value = str(item.get("value") or "").strip()
            if not key or not value:
                continue
            preferences[key] = self._merge_list_value(preferences.get(key), value)

        taboo_values = [str(item.get("content") or "").strip() for item in extracted.get("taboos", [])]
        preferences["topics_to_avoid"] = self._merge_string_lists(preferences.get("topics_to_avoid") or [], taboo_values)

        worry_values = [str(item.get("content") or "").strip() for item in extracted.get("worries", [])]
        if worry_values:
            emotional_patterns["recent_worries"] = self._merge_string_lists(
                emotional_patterns.get("recent_worries") or [],
                worry_values,
            )

        if extracted.get("emotion_trend"):
            emotional_patterns["recent_emotion_trend"] = str(extracted["emotion_trend"]).strip()

        milestone_values = [str(item.get("content") or "").strip() for item in extracted.get("milestones", [])]
        milestones = self._merge_string_lists(milestones, milestone_values)

        user.basic_info = basic_info
        user.emotional_patterns = emotional_patterns
        user.preferences = preferences
        user.relationship_milestones = milestones
        user.profile = {
            "basic_info": basic_info,
            "emotional_patterns": emotional_patterns,
            "relationship_milestones": milestones,
            "preferences": preferences,
        }

    def _update_short_term_memory(
        self,
        short_term: ShortTermMemory,
        user_message: str,
        agent_message: str,
        user_emotion: Dict,
        extracted: Dict[str, object],
    ) -> None:
        self._reset_daily_short_term_memory_if_needed(short_term)

        messages = list(short_term.messages or [])
        messages.extend(
            [
                {"role": "user", "content": user_message, "time": datetime.now().isoformat()},
                {"role": "assistant", "content": agent_message, "time": datetime.now().isoformat()},
            ]
        )
        max_messages = max(4, self.max_short_term_messages * 2)
        short_term.messages = messages[-max_messages:]
        short_term.today_chat_count = int(short_term.today_chat_count or 0) + 1
        short_term.user_mood_today = self._dominant_emotion(user_emotion)
        short_term.conversation_summary = str(extracted.get("short_term_summary") or short_term.conversation_summary or "")[:120]
        short_term.emotion_trend = str(extracted.get("emotion_trend") or short_term.emotion_trend or "未知")[:20]
        short_term.pending_topics = self._merge_string_lists(
            short_term.pending_topics or [],
            [str(item.get("content") or "").strip() for item in extracted.get("followups", [])],
            limit=6,
        )
        short_term.user_worries = self._merge_string_lists(
            short_term.user_worries or [],
            [str(item.get("content") or "").strip() for item in extracted.get("worries", [])],
            limit=6,
        )
        short_term.user_joys = self._merge_string_lists(
            short_term.user_joys or [],
            [str(item).strip() for item in extracted.get("user_joys", [])],
            limit=6,
        )

    def _upsert_memory_items(self, db, user: User, conversation_id: int, extracted: Dict[str, object]) -> None:
        created_items = self._build_memory_item_payloads(extracted, conversation_id)
        for payload in created_items:
            existing = (
                db.query(MemoryItem)
                .filter(
                    MemoryItem.user_id == user.id,
                    MemoryItem.memory_type == payload["memory_type"],
                    MemoryItem.content == payload["content"],
                )
                .first()
            )
            if existing:
                existing.salience = max(existing.salience or 0, payload["salience"])
                existing.confidence = max(existing.confidence or 0, payload["confidence"])
                existing.keywords = self._merge_string_lists(existing.keywords or [], payload["keywords"], limit=10)
                existing.entity_tags = self._merge_string_lists(existing.entity_tags or [], payload["entity_tags"], limit=10)
                existing.time_tags = self._merge_string_lists(existing.time_tags or [], payload["time_tags"], limit=10)
                existing.source_conversation_id = conversation_id
                continue

            db.add(
                MemoryItem(
                    user_id=user.id,
                    content=payload["content"],
                    memory_type=payload["memory_type"],
                    salience=payload["salience"],
                    confidence=payload["confidence"],
                    keywords=payload["keywords"],
                    entity_tags=payload["entity_tags"],
                    time_tags=payload["time_tags"],
                    source_conversation_id=conversation_id,
                    last_used_at=None,
                )
            )

    def _build_memory_item_payloads(self, extracted: Dict[str, object], conversation_id: int) -> List[Dict]:
        items: List[Dict] = []

        for item in extracted.get("identity_facts", []):
            key = str(item.get("key") or "").strip()
            value = str(item.get("value") or "").strip()
            if not key or not value:
                continue
            items.append(
                self._memory_item_payload(
                    memory_type="identity",
                    content=f"身份信息/{key}：{value}",
                    confidence=item.get("confidence", 0.5),
                    keywords=(item.get("keywords") or []) + self._extract_query_terms(value),
                    entity_tags=[key],
                    time_tags=[],
                )
            )

        for item in extracted.get("preferences", []):
            key = str(item.get("key") or "").strip()
            value = str(item.get("value") or "").strip()
            if not key or not value:
                continue
            items.append(
                self._memory_item_payload(
                    memory_type="preference",
                    content=f"偏好/{key}：{value}",
                    confidence=item.get("confidence", 0.5),
                    keywords=(item.get("keywords") or []) + self._extract_query_terms(value),
                    entity_tags=[key],
                    time_tags=[],
                )
            )

        for memory_type, field_name in (
            ("worry", "worries"),
            ("milestone", "milestones"),
            ("taboo", "taboos"),
            ("todo_followup", "followups"),
        ):
            for item in extracted.get(field_name, []):
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                items.append(
                    self._memory_item_payload(
                        memory_type=memory_type,
                        content=content,
                        confidence=item.get("confidence", 0.5),
                        keywords=(item.get("keywords") or []) + self._extract_query_terms(content),
                        entity_tags=[],
                        time_tags=self._extract_time_tags(content),
                    )
                )

        return items

    def _memory_item_payload(
        self,
        memory_type: str,
        content: str,
        confidence: object,
        keywords: Iterable[str],
        entity_tags: Iterable[str],
        time_tags: Iterable[str],
    ) -> Dict:
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.5
        confidence_score = max(0, min(100, int(confidence_value * 100)))
        return {
            "memory_type": memory_type,
            "content": content[:200],
            "salience": MEMORY_ITEM_SALIENCE.get(memory_type, 60),
            "confidence": confidence_score,
            "keywords": self._merge_string_lists([], list(keywords), limit=10),
            "entity_tags": self._merge_string_lists([], list(entity_tags), limit=10),
            "time_tags": self._merge_string_lists([], list(time_tags), limit=10),
        }

    def _select_relevant_memory_items(self, db, user_id: int, query_text: str, limit: int = 6) -> List[MemoryItem]:
        items = (
            db.query(MemoryItem)
            .filter(MemoryItem.user_id == user_id)
            .order_by(MemoryItem.updated_at.desc(), MemoryItem.salience.desc())
            .limit(60)
            .all()
        )
        if not items:
            return []

        query_terms = self._extract_query_terms(query_text)
        if not query_terms:
            ranked = sorted(
                items,
                key=lambda item: (item.salience or 0, item.confidence or 0, item.updated_at or item.created_at),
                reverse=True,
            )
            selected = ranked[:limit]
        else:
            scored = []
            for item in items:
                haystack = " ".join(
                    [
                        item.content or "",
                        " ".join(item.keywords or []),
                        " ".join(item.entity_tags or []),
                        " ".join(item.time_tags or []),
                    ]
                ).lower()
                match_score = 0
                for term in query_terms:
                    lowered = term.lower()
                    if lowered and lowered in haystack:
                        match_score += 18
                if match_score == 0 and len(query_terms) > 0:
                    continue
                scored.append(
                    (
                        match_score + int(item.salience or 0) + int((item.confidence or 0) * 0.6),
                        item,
                    )
                )
            scored.sort(key=lambda pair: pair[0], reverse=True)
            selected = [item for _, item in scored[:limit]]
            if not selected:
                selected = sorted(items, key=lambda item: item.salience or 0, reverse=True)[:limit]

        now = datetime.now()
        for item in selected:
            item.last_used_at = now
        db.commit()
        return selected

    def _extract_query_terms(self, text: str) -> List[str]:
        cleaned = sanitize_input(text)
        if not cleaned:
            return []

        terms = re.findall(r"[A-Za-z][A-Za-z0-9.+_/-]{1,24}", cleaned)
        for chunk in re.split(r"[，。！？、；：\s]+", cleaned):
            chunk = chunk.strip()
            if 2 <= len(chunk) <= 12:
                terms.append(chunk)

        unique: List[str] = []
        for term in terms:
            if term not in unique:
                unique.append(term)
        return unique[:12]

    def _extract_time_tags(self, text: str) -> List[str]:
        tags: List[str] = []
        for marker in ("今天", "今晚", "明天", "后天", "周末", "下周", "下个月"):
            if marker in text:
                tags.append(marker)
        return tags

    def _merge_scalar_value(self, current: object, new_value: str) -> str:
        current_text = sanitize_input(str(current or ""))
        if not current_text:
            return new_value
        if new_value in current_text:
            return current_text
        return f"{current_text}；{new_value}"

    def _merge_list_value(self, current: object, new_value: str):
        merged = self._merge_string_lists(current or [], [new_value], limit=10)
        return merged

    def _merge_string_lists(self, current: Iterable, incoming: Iterable, limit: int = 12) -> List[str]:
        merged: List[str] = []
        for source in (current, incoming):
            if isinstance(source, str):
                values = [item.strip() for item in re.split(r"[、；;,，]", source) if item.strip()]
            else:
                values = [str(item).strip() for item in source if str(item).strip()]
            for value in values:
                if value not in merged:
                    merged.append(value)
                if len(merged) >= limit:
                    return merged
        return merged

    def _dominant_emotion(self, user_emotion: Dict) -> str:
        if not user_emotion:
            return "neutral"
        return max(user_emotion.keys(), key=lambda key: user_emotion.get(key, 0))

    def _infer_emotion_trend(self, user_emotion: Dict) -> str:
        mood = self._dominant_emotion(user_emotion)
        mapping = {
            "happiness": "开心",
            "love": "暧昧",
            "tired": "疲惫",
            "stress": "焦虑",
            "anxiety": "焦虑",
            "sadness": "低落",
            "anger": "混合",
            "neutral": "平稳",
        }
        return mapping.get(mood, "未知")


# 全局记忆服务实例
memory_service = MemoryService()
