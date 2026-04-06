import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.models.database import SessionLocal, init_db
from app.models.user import MemoryItem, ShortTermMemory, User
from app.services.memory_service import memory_service


class MemoryServiceTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.wecom_user_id = f"memory-test-{uuid4().hex[:8]}"
        asyncio.run(memory_service.get_or_create_user(self.wecom_user_id))

    def tearDown(self):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.wecom_user_id == self.wecom_user_id).first()
            if not user:
                return

            db.query(MemoryItem).filter(MemoryItem.user_id == user.id).delete(synchronize_session=False)
            db.query(ShortTermMemory).filter(ShortTermMemory.user_id == user.id).delete(synchronize_session=False)
            db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def test_save_conversation_returns_conversation_id(self):
        conversation_id = asyncio.run(
            memory_service.save_conversation(
                user_id=self.wecom_user_id,
                user_message="今天有点累",
                agent_message="先抱一下你。",
                user_emotion={"tired": 0.9},
                agent_emotion={"current_mood": "caring", "intensity": 50},
            )
        )

        self.assertIsInstance(conversation_id, int)
        self.assertGreater(conversation_id, 0)

    def test_process_memory_update_persists_short_and_long_term_memory(self):
        conversation_id = asyncio.run(
            memory_service.save_conversation(
                user_id=self.wecom_user_id,
                user_message="我最近加班压力很大，明天面试结果出来，别提前任。",
                agent_message="先抱一下你，明天我陪你等结果。",
                user_emotion={"anxiety": 0.7, "stress": 0.3},
                agent_emotion={"current_mood": "caring", "intensity": 68},
            )
        )

        llm_result = {
            "identity_facts": [{"key": "work_type", "value": "产品经理", "confidence": 0.92, "keywords": ["产品经理"]}],
            "preferences": [{"key": "likes", "value": "日料", "confidence": 0.81, "keywords": ["日料"]}],
            "worries": [{"content": "最近加班压力很大", "confidence": 0.93, "keywords": ["加班", "压力"]}],
            "milestones": [{"content": "上周第一次一起看电影", "confidence": 0.79, "keywords": ["看电影"]}],
            "taboos": [{"content": "前任", "confidence": 0.91, "keywords": ["前任"]}],
            "followups": [{"content": "明天面试结果出来", "confidence": 0.84, "keywords": ["明天", "面试"]}],
            "short_term_summary": "最近加班压力很大，明天要等面试结果。",
            "emotion_trend": "焦虑",
            "user_joys": ["上周第一次一起看电影"],
        }

        with (
            patch.object(memory_service, "_should_use_llm_memory_extraction", return_value=True),
            patch("app.services.llm_service.glm_service.extract_memory_facts", AsyncMock(return_value=llm_result)),
        ):
            asyncio.run(
                memory_service.process_memory_update(
                    wecom_user_id=self.wecom_user_id,
                    conversation_id=conversation_id,
                    user_message="我最近加班压力很大，明天面试结果出来，别提前任。",
                    agent_message="先抱一下你，明天我陪你等结果。",
                    user_emotion={"anxiety": 0.7, "stress": 0.3},
                    agent_emotion={"current_mood": "caring", "intensity": 68},
                )
            )

        payload = asyncio.run(memory_service.get_user_memory(self.wecom_user_id, query_text="面试结果"))
        self.assertIsNotNone(payload)
        self.assertEqual(payload["basic_info"]["work_type"], "产品经理")
        self.assertIn("日料", payload["preferences"]["likes"])
        self.assertIn("前任", payload["preferences"]["topics_to_avoid"])
        self.assertIn("上周第一次一起看电影", payload["relationship_milestones"])

        short_term_memory = payload["short_term_memory"]
        self.assertEqual(short_term_memory["emotion_trend"], "焦虑")
        self.assertIn("明天面试结果出来", short_term_memory["pending_topics"])
        self.assertIn("最近加班压力很大", short_term_memory["user_worries"])
        self.assertIn("上周第一次一起看电影", short_term_memory["user_joys"])

        relevant_items = payload["memory_items"]
        self.assertTrue(any(item["content"] == "明天面试结果出来" for item in relevant_items))
        self.assertTrue(any(item["type"] == "todo_followup" for item in relevant_items))

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.wecom_user_id == self.wecom_user_id).first()
            item_count = db.query(MemoryItem).filter(MemoryItem.user_id == user.id).count()
            short_term = db.query(ShortTermMemory).filter(ShortTermMemory.user_id == user.id).first()
        finally:
            db.close()

        self.assertGreaterEqual(item_count, 5)
        self.assertIsNotNone(short_term)
        self.assertGreaterEqual(short_term.today_chat_count, 1)


if __name__ == "__main__":
    unittest.main()
