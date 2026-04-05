import unittest

from app.utils.helpers import (
    choose_natural_fallback_reply,
    get_response_constraints,
    is_response_too_similar,
    summarize_recent_agent_replies,
)


class ResponseConstraintTests(unittest.TestCase):
    def test_short_input_prefers_short_reply(self):
        result = get_response_constraints("晚安")
        self.assertEqual(result["style"], "ultra_short")
        self.assertLessEqual(result["max_tokens"], 48)

    def test_long_input_allows_longer_reply(self):
        result = get_response_constraints(
            "今天工作真的有点累，还遇到了几个很烦的事情，想和你聊聊。"
            "我有点不知道怎么处理，也有点焦虑，想听听你的看法。"
        )
        self.assertIn(result["style"], {"medium", "long"})
        self.assertGreaterEqual(result["max_tokens"], 128)

    def test_summarize_recent_agent_replies_skips_duplicates_and_short_text(self):
        result = summarize_recent_agent_replies(
            ["好", "我在呢[抱抱]，你继续说，我认真听着。", "我在呢，你继续说，我认真听着。", "晚点和我说说今天发生了什么吧"],
            limit=3,
        )
        self.assertEqual(len(result), 2)
        self.assertIn("我在呢[抱抱]，你继续说，我认真听着。", result)

    def test_is_response_too_similar_detects_repeated_prefix(self):
        self.assertTrue(
            is_response_too_similar(
                "我在呢[抱抱]，你继续说，我认真听着。",
                ["我在呢，你接着说，我有在听。"],
            )
        )

    def test_choose_natural_fallback_reply_varies_by_emotion(self):
        caring = choose_natural_fallback_reply("今天真的好累", {"tired": 0.9})
        romantic = choose_natural_fallback_reply("想你了", {"love": 0.9})
        neutral = choose_natural_fallback_reply("在吗", {"neutral": 1.0})

        self.assertIn("认真听着", caring)
        self.assertIn("再多和我说一点", romantic)
        self.assertEqual(neutral, "我在呢，你接着说，我有在听。")


if __name__ == "__main__":
    unittest.main()
