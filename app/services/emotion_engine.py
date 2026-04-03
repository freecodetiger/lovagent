"""
情绪引擎服务
"""

from typing import Dict, Optional, List
from datetime import datetime
import json

from app.models.user import EmotionState
from app.models.database import SessionLocal


class EmotionEngine:
    """情绪状态引擎"""

    # 情绪状态定义
    EMOTION_STATES = {
        "happy": {
            "name": "开心",
            "triggers": ["开心", "好消息", "成功", "完成", "太好了", "耶", "哈哈"],
            "base_response": "嘿嘿，听你这么说我也很开心[偷笑]",
        },
        "caring": {
            "name": "关心",
            "triggers": ["累", "辛苦", "难过", "不舒服", "生病", "烦恼", "压力"],
            "base_response": "我在这儿呢[抱抱]，要不要跟我说说发生了什么？",
        },
        "playful": {
            "name": "俏皮",
            "triggers": ["开玩笑", "调皮", "哈哈", "搞笑", "逗", "好玩"],
            "base_response": "才不是呢[撇嘴]",
        },
        "jealous": {
            "name": "吃醋",
            "triggers": ["其他女生", "别人", "闺蜜", "同事"],
            "base_response": "哼，你是不是对别人也这么说[吃醋]",
        },
        "worried": {
            "name": "担心",
            "triggers": ["消失", "熬夜", "不睡", "通宵", "危险", "担心"],
            "base_response": "我有点担心你，要不要我陪你聊聊？",
        },
        "romantic": {
            "name": "浪漫",
            "triggers": ["想你", "爱你", "抱抱", "晚安", "早安", "亲亲", "宝贝"],
            "base_response": "我也好想你[心]",
        },
        "upset": {
            "name": "小情绪",
            "triggers": ["不理我", "不回我", "忽视"],
            "base_response": "哼，你都不理我[委屈]",
        },
        "missing": {
            "name": "思念",
            "triggers": ["想你", "好久没聊", "想念", "思念"],
            "base_response": "我也好想你，刚刚还在想你呢[抱抱]",
        },
    }

    # 情绪强度阈值
    LOW_THRESHOLD = 30
    MEDIUM_THRESHOLD = 70
    HIGH_THRESHOLD = 100

    def __init__(self):
        self.db = SessionLocal()

    def detect_emotion_trigger(self, text: str) -> Optional[str]:
        """检测文本中的情绪触发词"""
        text_lower = text.lower()

        for emotion, info in self.EMOTION_STATES.items():
            for trigger in info["triggers"]:
                if trigger in text_lower:
                    return emotion

        return None

    def get_emotion_state(self, user_id: str) -> EmotionState:
        """获取用户的情绪状态"""
        # 这里简化处理，实际应该从数据库查询
        # 需要先获取 user 的实际 id（通过 wecom_user_id）
        return self._get_default_emotion_state()

    def _get_default_emotion_state(self) -> Dict:
        """获取默认情绪状态"""
        return {
            "current_mood": "happy",
            "intensity": 20,
            "happy_intensity": 20,
            "caring_intensity": 10,
            "playful_intensity": 15,
            "jealous_intensity": 0,
            "worried_intensity": 5,
            "romantic_intensity": 30,
            "upset_intensity": 0,
            "missing_intensity": 10,
        }

    async def update_state(
        self,
        user_id: str,
        user_input: str,
        user_emotion: Dict[str, float],
    ) -> Dict:
        """
        根据用户输入更新情绪状态

        Args:
            user_id: 用户 ID
            user_input: 用户输入文本
            user_emotion: 用户情绪分析结果

        Returns:
            更新后的情绪状态
        """
        current_state = self.get_emotion_state(user_id)

        # 检测触发词
        triggered_emotion = self.detect_emotion_trigger(user_input)

        # 根据用户情绪调整 Agent 情绪
        if user_emotion:
            # 用户开心 -> Agent 也开心
            if user_emotion.get("happiness", 0) > 0.5:
                current_state["happy_intensity"] = min(100, current_state["happy_intensity"] + 20)
                current_state["current_mood"] = "happy"

            # 用户难过 -> Agent 关心
            if user_emotion.get("sadness", 0) > 0.5:
                current_state["caring_intensity"] = min(100, current_state["caring_intensity"] + 30)
                current_state["current_mood"] = "caring"

            # 用户焦虑 -> Agent 担心
            if user_emotion.get("anxiety", 0) > 0.5:
                current_state["worried_intensity"] = min(100, current_state["worried_intensity"] + 25)
                current_state["current_mood"] = "worried"

            # 用户表达爱/思念 -> Agent 浪漫
            if user_emotion.get("love", 0) > 0.5:
                current_state["romantic_intensity"] = min(100, current_state["romantic_intensity"] + 25)
                current_state["current_mood"] = "romantic"

            # 用户疲惫 -> Agent 关心 + 担心
            if user_emotion.get("tired", 0) > 0.5:
                current_state["caring_intensity"] = min(100, current_state["caring_intensity"] + 25)
                current_state["worried_intensity"] = min(100, current_state["worried_intensity"] + 20)
                current_state["current_mood"] = "caring"

        # 触发词匹配
        if triggered_emotion:
            current_state[f"{triggered_emotion}_intensity"] = min(
                100, current_state.get(f"{triggered_emotion}_intensity", 0) + 30
            )
            current_state["current_mood"] = triggered_emotion

        # 计算当前情绪强度
        current_mood = current_state["current_mood"]
        current_state["intensity"] = current_state.get(f"{current_mood}_intensity", 0)

        # 情绪衰减（非当前情绪强度降低）
        for emotion in self.EMOTION_STATES.keys():
            if emotion != current_mood:
                current_state[f"{emotion}_intensity"] = max(
                    0, current_state.get(f"{emotion}_intensity", 0) - 10
                )

        return current_state

    def get_response_strategy(self, emotion_state: Dict) -> str:
        """根据情绪状态获取响应策略"""
        mood = emotion_state.get("current_mood", "happy")
        intensity = emotion_state.get("intensity", 0)

        if intensity < self.LOW_THRESHOLD:
            return "natural_conversation"
        elif intensity < self.MEDIUM_THRESHOLD:
            return "emotional_response"
        else:
            return "intense_emotional_response"


# 全局情绪引擎实例
emotion_engine = EmotionEngine()