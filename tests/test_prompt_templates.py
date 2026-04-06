import unittest

from app.prompts.templates import build_dynamic_prompt


class PromptTemplateTests(unittest.TestCase):
    def test_build_dynamic_prompt_includes_recent_reply_anti_repeat_rules(self):
        prompt = build_dynamic_prompt(
            user_input="今天有点累",
            user_emotion={"tired": 0.8, "neutral": 0.2},
            agent_emotion={"current_mood": "caring", "intensity": 55},
            context={"today_chat_count": 2, "last_chat_time": None},
            current_time="2026-04-05 22:00:00",
            recent_agent_replies=[
                "我在呢[抱抱]，你继续说，我认真听着。",
                "听起来你今天真的很辛苦。",
            ],
        )

        self.assertIn("Recent Reply Signals", prompt)
        self.assertIn("最近说过：我在呢[抱抱]，你继续说，我认真听着。", prompt)
        self.assertIn("明确避免复用最近几轮相同开头、相同安慰句、相同收尾、相同表情组合", prompt)
        self.assertIn("不要把“情绪表达方向”直接写成固定台词", prompt)
        self.assertNotIn("情绪表达建议:", prompt)

    def test_build_dynamic_prompt_uses_custom_response_preferences(self):
        prompt = build_dynamic_prompt(
            user_input="今天真的有点累啊",
            user_emotion={"tired": 0.8, "neutral": 0.2},
            agent_emotion={"current_mood": "caring", "intensity": 55},
            context={"today_chat_count": 2, "last_chat_time": None},
            current_time="2026-04-05 22:00:00",
            persona_config={
                "display_name": "小甜",
                "response_preferences": {
                    "ultra_short_max_chars": 36,
                    "short_max_chars": 120,
                    "medium_max_chars": 150,
                    "long_max_chars": 180,
                },
            },
        )

        self.assertIn("短回 120 字内", prompt)
        self.assertIn("最多不超过 120 个汉字", prompt)

    def test_build_dynamic_prompt_includes_web_search_context(self):
        prompt = build_dynamic_prompt(
            user_input="AlphaFold 是什么",
            user_emotion={"neutral": 1.0},
            agent_emotion={"current_mood": "happy", "intensity": 40},
            context={},
            current_time="2026-04-06 00:00:00",
            web_search_context={
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
            },
        )

        self.assertIn("Web Search Context", prompt)
        self.assertIn("检索词：AlphaFold 是什么", prompt)
        self.assertIn("AlphaFold - DeepMind", prompt)
        self.assertIn("优先参考检索结果，不要编造", prompt)


if __name__ == "__main__":
    unittest.main()
