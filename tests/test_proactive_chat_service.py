import unittest
from datetime import datetime, timedelta

from app.models.admin import ProactiveChatLog
from app.models.database import SessionLocal, init_db
from app.models.user import User
from app.services.proactive_chat_service import proactive_chat_service


class ProactiveChatServiceTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.user = self.db.query(User).filter(User.wecom_user_id == "proactive-user").first()
        if not self.user:
            now = datetime.now() - timedelta(hours=8)
            self.user = User(
                wecom_user_id="proactive-user",
                nickname="阿李",
                profile={},
                basic_info={},
                emotional_patterns={},
                relationship_milestones=[],
                preferences={},
                total_conversations=1,
                first_interaction=now,
                last_interaction=now,
            )
            self.db.add(self.user)
            self.db.commit()
            self.db.refresh(self.user)

    def tearDown(self):
        self.db.query(ProactiveChatLog).filter(ProactiveChatLog.target_wecom_user_id == "proactive-user").delete(
            synchronize_session=False
        )
        user = self.db.query(User).filter(User.wecom_user_id == "proactive-user").first()
        if user:
            self.db.delete(user)
        self.db.commit()
        self.db.close()

    def test_resolve_due_trigger_matches_current_scheduled_window(self):
        config = {
            "enabled": True,
            "target_wecom_user_id": "proactive-user",
            "scheduled_windows": [
                {"key": "now", "label": "现在", "enabled": True, "time": datetime.now().strftime("%H:%M")}
            ],
            "inactivity_trigger_hours": 24,
            "quiet_hours": {"enabled": False, "start": "23:00", "end": "09:00"},
            "max_messages_per_day": 4,
            "min_interval_minutes": 30,
            "tone_hint": "",
        }

        result = proactive_chat_service._resolve_due_trigger(config)
        self.assertIsNotNone(result)
        self.assertEqual(result["trigger_type"], "scheduled")

    def test_resolve_due_trigger_respects_quiet_hours(self):
        now = datetime.now()
        start = (now - timedelta(minutes=1)).strftime("%H:%M")
        end = (now + timedelta(minutes=1)).strftime("%H:%M")
        config = {
            "enabled": True,
            "target_wecom_user_id": "proactive-user",
            "scheduled_windows": [
                {"key": "now", "label": "现在", "enabled": True, "time": now.strftime("%H:%M")}
            ],
            "inactivity_trigger_hours": 24,
            "quiet_hours": {"enabled": True, "start": start, "end": end},
            "max_messages_per_day": 4,
            "min_interval_minutes": 30,
            "tone_hint": "",
        }

        result = proactive_chat_service._resolve_due_trigger(config)
        self.assertIsNone(result)

    def test_resolve_due_trigger_skips_repeat_inactivity_without_new_interaction(self):
        inactivity_sent_at = datetime.now() - timedelta(hours=2)
        self.db.add(
            ProactiveChatLog(
                target_wecom_user_id="proactive-user",
                trigger_type="inactivity",
                window_key=None,
                content="刚刚想到你了",
                status="sent",
                sent_at=inactivity_sent_at,
            )
        )
        self.db.commit()

        config = {
            "enabled": True,
            "target_wecom_user_id": "proactive-user",
            "scheduled_windows": [],
            "inactivity_trigger_hours": 6,
            "quiet_hours": {"enabled": False, "start": "23:00", "end": "09:00"},
            "max_messages_per_day": 4,
            "min_interval_minutes": 30,
            "tone_hint": "",
        }

        result = proactive_chat_service._resolve_due_trigger(config)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
