import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.admin import AgentConfig, ProactiveChatConfig, ProactiveChatLog
from app.models.database import SessionLocal
from app.models.database import init_db
from app.models.user import User
from app.prompts.templates import build_dynamic_prompt, build_proactive_prompt
from app.services.persona_service import DEFAULT_PERSONA_CONFIG_KEY
from app.services.proactive_chat_service import DEFAULT_PROACTIVE_CHAT_CONFIG_KEY
from app.services.runtime_config_service import runtime_config_service


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.original_persona = (
            self.db.query(AgentConfig)
            .filter(AgentConfig.config_key == DEFAULT_PERSONA_CONFIG_KEY)
            .first()
        )
        if self.original_persona:
            self.original_persona_snapshot = {
                "display_name": self.original_persona.display_name,
                "persona_core": dict(self.original_persona.persona_core or {}),
                "persona_text": self.original_persona.persona_text,
                "personality_metrics": dict(self.original_persona.personality_metrics or {}),
                "topics_to_avoid": list(self.original_persona.topics_to_avoid or []),
                "recommended_topics": list(self.original_persona.recommended_topics or []),
                "response_rules": list(self.original_persona.response_rules or []),
                "response_preferences": dict((self.original_persona.persona_core or {}).get("_response_preferences") or {}),
            }
        else:
            self.original_persona_snapshot = None
        self.original_proactive = (
            self.db.query(ProactiveChatConfig)
            .filter(ProactiveChatConfig.config_key == DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
            .first()
        )
        if self.original_proactive:
            self.original_proactive_snapshot = {
                "enabled": self.original_proactive.enabled,
                "target_wecom_user_id": self.original_proactive.target_wecom_user_id,
                "scheduled_windows": list(self.original_proactive.scheduled_windows or []),
                "inactivity_trigger_hours": self.original_proactive.inactivity_trigger_hours,
                "quiet_hours": dict(self.original_proactive.quiet_hours or {}),
                "max_messages_per_day": self.original_proactive.max_messages_per_day,
                "min_interval_minutes": self.original_proactive.min_interval_minutes,
                "tone_hint": self.original_proactive.tone_hint,
            }
        else:
            self.original_proactive_snapshot = None
        self.client = TestClient(app)
        self.password_patcher = patch.object(settings, "admin_password", "test-admin")
        self.password_patcher.start()
        self.runtime_password_patcher = patch.object(
            runtime_config_service,
            "get_effective_admin_password",
            return_value="test-admin",
        )
        self.runtime_password_patcher.start()

    def tearDown(self):
        test_user = self.db.query(User).filter(User.wecom_user_id == "test-user").first()
        if test_user:
            self.db.delete(test_user)
            self.db.commit()

        current_persona = (
            self.db.query(AgentConfig)
            .filter(AgentConfig.config_key == DEFAULT_PERSONA_CONFIG_KEY)
            .first()
        )

        if self.original_persona_snapshot:
            if not current_persona:
                current_persona = AgentConfig(config_key=DEFAULT_PERSONA_CONFIG_KEY)
                self.db.add(current_persona)

            restored_persona_core = dict(self.original_persona_snapshot["persona_core"])
            restored_persona_core["_response_preferences"] = self.original_persona_snapshot["response_preferences"]
            current_persona.display_name = self.original_persona_snapshot["display_name"]
            current_persona.persona_core = restored_persona_core
            current_persona.persona_text = self.original_persona_snapshot["persona_text"]
            current_persona.personality_metrics = self.original_persona_snapshot["personality_metrics"]
            current_persona.topics_to_avoid = self.original_persona_snapshot["topics_to_avoid"]
            current_persona.recommended_topics = self.original_persona_snapshot["recommended_topics"]
            current_persona.response_rules = self.original_persona_snapshot["response_rules"]
            self.db.commit()
        elif current_persona:
            self.db.delete(current_persona)
            self.db.commit()

        current_proactive = (
            self.db.query(ProactiveChatConfig)
            .filter(ProactiveChatConfig.config_key == DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
            .first()
        )
        if self.original_proactive_snapshot:
            if not current_proactive:
                current_proactive = ProactiveChatConfig(config_key=DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
                self.db.add(current_proactive)

            current_proactive.enabled = self.original_proactive_snapshot["enabled"]
            current_proactive.target_wecom_user_id = self.original_proactive_snapshot["target_wecom_user_id"]
            current_proactive.scheduled_windows = self.original_proactive_snapshot["scheduled_windows"]
            current_proactive.inactivity_trigger_hours = self.original_proactive_snapshot["inactivity_trigger_hours"]
            current_proactive.quiet_hours = self.original_proactive_snapshot["quiet_hours"]
            current_proactive.max_messages_per_day = self.original_proactive_snapshot["max_messages_per_day"]
            current_proactive.min_interval_minutes = self.original_proactive_snapshot["min_interval_minutes"]
            current_proactive.tone_hint = self.original_proactive_snapshot["tone_hint"]
            self.db.commit()
        elif current_proactive:
            self.db.delete(current_proactive)
            self.db.commit()

        self.db.query(ProactiveChatLog).filter(ProactiveChatLog.target_wecom_user_id.in_(["test-user", "user-1"])).delete(
            synchronize_session=False
        )
        self.db.commit()

        self.db.close()
        self.password_patcher.stop()
        self.runtime_password_patcher.stop()
        self.client.close()

    def login(self):
        response = self.client.post("/admin-api/auth/login", json={"password": "test-admin"})
        self.assertEqual(response.status_code, 200)

    def test_login_and_persona_read(self):
        unauthorized = self.client.get("/admin-api/persona")
        self.assertEqual(unauthorized.status_code, 401)

        self.login()
        response = self.client.get("/admin-api/persona")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("display_name", payload)
        self.assertIn("personality_metrics", payload)
        self.assertNotIn("_response_preferences", payload["persona_core"])

    def test_persona_save_and_preview_prompt(self):
        self.login()
        payload = {
            "display_name": "测试小猫",
            "persona_core": {
                "role": "你是我的恋爱搭子。",
                "persona_summary": "嘴甜，松弛，有点黏人。",
                "aesthetic": "爱拍照，也爱聊电影。",
                "lifestyle": "会关心作息和吃饭。",
                "opening_style": "先抱一下再接话。",
                "signature_style": "自然、轻松、有点俏皮。",
                "emoji_style": "适度用 [心] 和 [抱抱]。",
            },
            "personality_metrics": {
                "温柔指数": 92,
                "俏皮程度": 76,
                "独立性": 60,
                "依赖感": 80,
                "理性程度": 45,
                "感性程度": 88,
            },
            "interests": ["摄影", "电影"],
            "values": ["陪伴", "真诚"],
            "topics_to_avoid": ["冷暴力"],
            "recommended_topics": ["吃饭", "今天的心情"],
            "response_rules": ["先接住情绪，再回应内容。"],
            "response_preferences": {
                "ultra_short_max_chars": 36,
                "short_max_chars": 120,
                "medium_max_chars": 150,
                "long_max_chars": 180,
            },
        }

        save_response = self.client.put("/admin-api/persona", json=payload)
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_response.json()["display_name"], "测试小猫")
        self.assertEqual(save_response.json()["response_preferences"]["short_max_chars"], 120)
        self.assertNotIn("_response_preferences", save_response.json()["persona_core"])

        preview_response = self.client.post(
            "/admin-api/persona/preview-prompt",
            json={"user_message": "今天有点累", "draft_config": payload},
        )
        self.assertEqual(preview_response.status_code, 200)
        prompt = preview_response.json()["prompt"]
        self.assertIn("测试小猫", prompt)
        self.assertIn("先接住情绪，再回应内容。", prompt)
        self.assertIn("短回 120 字内", prompt)

    def test_preview_reply_uses_custom_response_preferences_for_max_tokens(self):
        self.login()
        payload = {
            "user_message": "今天真的有点累啊",
            "draft_config": {
                "display_name": "测试小猫",
                "response_preferences": {
                    "ultra_short_max_chars": 36,
                    "short_max_chars": 120,
                    "medium_max_chars": 150,
                    "long_max_chars": 180,
                },
            },
        }

        with (
            patch("app.routers.admin.glm_service.analyze_emotion", AsyncMock(return_value={"tired": 0.8})),
            patch(
                "app.routers.admin.emotion_engine.update_state",
                AsyncMock(return_value={"current_mood": "caring", "intensity": 60}),
            ),
            patch(
                "app.routers.admin.glm_service.chat_with_context",
                AsyncMock(return_value="先抱一下你，慢慢和我说，我会认真听完的。"),
            ) as chat_mock,
        ):
            response = self.client.post("/admin-api/persona/preview-reply", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(chat_mock.await_args.kwargs["max_tokens"], 192)

    def test_preview_prompt_includes_web_search_context(self):
        self.login()
        payload = {"user_message": "AlphaFold 是什么"}

        with patch(
            "app.graph.tools.search.web_search_service.maybe_collect_web_context",
            AsyncMock(
                return_value={
                    "triggered": True,
                    "query": "AlphaFold 是什么",
                    "results": [
                        {
                            "title": "AlphaFold - DeepMind",
                            "media": "DeepMind",
                            "publish_date": "2024-01-01",
                            "content": "AlphaFold 是一个蛋白质结构预测系统。",
                            "link": "https://example.com/alphafold",
                        }
                    ],
                }
            ),
        ):
            response = self.client.post("/admin-api/persona/preview-prompt", json=payload)

        self.assertEqual(response.status_code, 200)
        prompt = response.json()["prompt"]
        self.assertIn("Web Search Context", prompt)
        self.assertIn("AlphaFold - DeepMind", prompt)

    def test_persona_read_hides_legacy_internal_field_and_parses_legacy_string(self):
        current_persona = (
            self.db.query(AgentConfig)
            .filter(AgentConfig.config_key == DEFAULT_PERSONA_CONFIG_KEY)
            .first()
        )
        if not current_persona:
            current_persona = AgentConfig(config_key=DEFAULT_PERSONA_CONFIG_KEY)
            self.db.add(current_persona)

        current_persona.display_name = "旧档案"
        current_persona.persona_core = {
            "role": "旧角色",
            "persona_summary": "旧设定",
            "aesthetic": "旧审美",
            "lifestyle": "旧生活",
            "opening_style": "旧开场",
            "signature_style": "旧风格",
            "emoji_style": "旧表情",
            "_response_preferences": "{'ultra_short_max_chars': 36, 'short_max_chars': 120, 'medium_max_chars': 150, 'long_max_chars': 180}",
        }
        current_persona.personality_metrics = {}
        current_persona.topics_to_avoid = []
        current_persona.recommended_topics = []
        current_persona.response_rules = []
        self.db.commit()

        self.login()
        response = self.client.get("/admin-api/persona")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("_response_preferences", payload["persona_core"])
        self.assertEqual(payload["response_preferences"]["short_max_chars"], 120)

    def test_user_memory_upsert(self):
        self.login()
        payload = {
            "nickname": "小李",
            "avatar_url": "",
            "basic_info": {"work_type": "设计师"},
            "emotional_patterns": {"comfort_needs": "被认真听完"},
            "relationship_milestones": ["第一次说晚安"],
            "preferences": {"chat_style": "温柔但别太肉麻"},
        }

        save_response = self.client.put("/admin-api/users/test-user/memory", json=payload)
        self.assertEqual(save_response.status_code, 200)

        get_response = self.client.get("/admin-api/users/test-user/memory")
        self.assertEqual(get_response.status_code, 200)
        memory = get_response.json()
        self.assertEqual(memory["nickname"], "小李")
        self.assertEqual(memory["basic_info"]["work_type"], "设计师")
        self.assertIn("第一次说晚安", memory["relationship_milestones"])

    def test_proactive_chat_config_save_and_preview(self):
        self.login()
        payload = {
            "enabled": True,
            "target_wecom_user_id": "test-user",
            "scheduled_windows": [
                {"key": "morning", "label": "上午", "enabled": True, "time": "09:30"},
                {"key": "afternoon", "label": "下午", "enabled": False, "time": "15:00"},
                {"key": "night", "label": "夜晚", "enabled": True, "time": "21:00"},
            ],
            "inactivity_trigger_hours": 8,
            "quiet_hours": {"enabled": True, "start": "23:00", "end": "09:00"},
            "max_messages_per_day": 3,
            "min_interval_minutes": 240,
            "tone_hint": "像突然想到我一样，轻一点。",
        }

        save_response = self.client.put("/admin-api/proactive-chat", json=payload)
        self.assertEqual(save_response.status_code, 200)
        self.assertTrue(save_response.json()["enabled"])
        self.assertEqual(save_response.json()["target_wecom_user_id"], "test-user")

        with patch(
            "app.routers.admin.proactive_chat_service.preview_outreach",
            AsyncMock(return_value={"prompt": "proactive prompt", "reply": "刚刚突然想到你了。", "delivery": {"status": "preview"}}),
        ):
            preview_response = self.client.post("/admin-api/proactive-chat/preview", json={"wecom_user_id": "test-user"})

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.json()["reply"], "刚刚突然想到你了。")

    def test_proactive_chat_run_once_endpoint(self):
        self.login()

        with patch(
            "app.routers.admin.proactive_chat_service.run_outreach_once",
            AsyncMock(
                return_value={
                    "prompt": "proactive prompt",
                    "reply": "刚刚想起你啦。",
                    "delivery": {"attempted": True, "status": "sent"},
                }
            ),
        ):
            response = self.client.post("/admin-api/proactive-chat/run-once", json={"wecom_user_id": "test-user"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery"]["status"], "sent")


class PromptCompositionTests(unittest.TestCase):
    def test_build_dynamic_prompt_includes_persona_and_memory(self):
        prompt = build_dynamic_prompt(
            user_input="我今天有点低落",
            user_emotion={"sadness": 0.8, "neutral": 0.2},
            agent_emotion={"current_mood": "caring", "intensity": 70},
            context={"today_chat_count": 1, "last_chat_time": None},
            current_time="2026-04-06 00:00:00",
            recent_agent_replies=["刚才已经安慰过一句"],
            persona_config={
                "display_name": "星星",
                "persona_core": {
                    "role": "你是一个会安静陪伴我的恋爱伴侣。",
                    "persona_summary": "温柔但不黏腻。",
                    "aesthetic": "偏爱电影和夜晚散步。",
                    "lifestyle": "会提醒我早点睡。",
                    "opening_style": "先安静抱一下再开口。",
                    "signature_style": "轻声、具体、不要模板化。",
                    "emoji_style": "少量用 [抱抱]。",
                },
                "personality_metrics": {"温柔指数": 90},
                "interests": ["电影"],
                "values": ["陪伴"],
                "topics_to_avoid": ["说教"],
                "recommended_topics": ["今天发生了什么"],
                "response_rules": ["先接住情绪。"],
            },
            user_profile={
                "nickname": "阿李",
                "basic_info": {"work_type": "程序员"},
                "emotional_patterns": {"comfort_needs": ["倾听", "安静陪伴"]},
                "relationship_milestones": ["第一次主动说想我"],
                "preferences": {"chat_style": "短句一点"},
            },
        )

        self.assertIn("名字：星星", prompt)
        self.assertIn("用户昵称：阿李", prompt)
        self.assertIn("基础信息/work_type：程序员", prompt)
        self.assertIn("关系里程碑 1：第一次主动说想我", prompt)

    def test_build_proactive_prompt_includes_mode_and_memory(self):
        prompt = build_proactive_prompt(
            trigger_type="inactivity",
            current_time="2026-04-06 20:00:00",
            user_profile={
                "nickname": "阿李",
                "basic_info": {"work_type": "程序员"},
                "relationship_milestones": ["第一次主动说想我"],
            },
            context={"today_chat_count": 1, "last_chat_time": None},
            recent_agent_replies=["今天已经说过一句安慰了"],
            tone_hint="像突然想起他一样。",
        )

        self.assertIn("Proactive Chat Mode", prompt)
        self.assertIn("触发类型: inactivity", prompt)
        self.assertIn("用户昵称：阿李", prompt)
        self.assertIn("关系里程碑 1：第一次主动说想我", prompt)


if __name__ == "__main__":
    unittest.main()
