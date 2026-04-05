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


if __name__ == "__main__":
    unittest.main()
