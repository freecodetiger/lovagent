"""
工具函数模块
"""

from datetime import datetime
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional


def get_current_time() -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time_period() -> str:
    """根据当前时间获取时间段"""
    hour = datetime.now().hour
    if 6 <= hour < 9:
        return "早晨"
    elif 9 <= hour < 12:
        return "上午"
    elif 12 <= hour < 18:
        return "下午"
    elif 18 <= hour < 21:
        return "傍晚"
    elif 21 <= hour < 24:
        return "夜晚"
    else:
        return "深夜"


def get_time_period_behavior(time_period: str) -> str:
    """根据时间段获取行为特征描述"""
    behaviors = {
        "早晨": "温柔问候，关心睡眠和早餐",
        "上午": "鼓励工作/学习，偶尔调皮",
        "下午": "分享生活，询问近况",
        "傍晚": "关心晚餐，分享黄昏心情",
        "夜晚": "深情交流，表达思念",
        "深夜": "担心熬夜，温柔劝阻",
    }
    return behaviors.get(time_period, "自然交流")


def format_duration(seconds: int) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}小时"
    else:
        days = seconds // 86400
        return f"{days}天"


def calculate_days_since(start_date: datetime) -> int:
    """计算从指定日期至今的天数"""
    return (datetime.now() - start_date).days


def truncate_text(text: str, max_length: int) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_input(text: str) -> str:
    """清理用户输入"""
    # 移除多余的空白字符
    text = text.strip()
    # 移除可能导致问题的字符
    text = text.replace("\x00", "")
    return text


def get_response_constraints(text: str, response_preferences: Optional[Dict[str, int]] = None) -> Dict[str, object]:
    """
    根据用户输入长度和复杂度，动态约束回复长度与生成参数。
    """
    cleaned = sanitize_input(text)
    length = len(cleaned)
    question_markers = ("?", "？", "吗", "呢", "么", "什么", "怎么", "为什么", "要不要", "是不是")
    has_question = any(marker in cleaned for marker in question_markers)
    has_line_break = "\n" in cleaned
    preferences = _merge_response_preferences(response_preferences)

    ultra_short_max_chars = preferences["ultra_short_max_chars"]
    short_max_chars = preferences["short_max_chars"]
    medium_max_chars = preferences["medium_max_chars"]
    long_max_chars = preferences["long_max_chars"]

    if length <= 6 and not has_question and not has_line_break:
        return {
            "style": "ultra_short",
            "instruction": f"这轮只回 1 句短回复，10-{ultra_short_max_chars} 个汉字左右，最多不超过 {ultra_short_max_chars} 个汉字。",
            "max_chars": ultra_short_max_chars,
            "max_tokens": _estimate_max_tokens(ultra_short_max_chars, minimum=48),
            "context_limit": 2,
        }

    if length <= 18 and not has_line_break:
        return {
            "style": "short",
            "instruction": f"这轮优先回 1 句，必要时最多 2 句，18-{short_max_chars} 个汉字左右，最多不超过 {short_max_chars} 个汉字。",
            "max_chars": short_max_chars,
            "max_tokens": _estimate_max_tokens(short_max_chars, minimum=80),
            "context_limit": 3,
        }

    if length <= 60 and not has_line_break:
        return {
            "style": "medium",
            "instruction": f"这轮回 1-2 句自然微信式回复，30-{medium_max_chars} 个汉字左右，最多不超过 {medium_max_chars} 个汉字。",
            "max_chars": medium_max_chars,
            "max_tokens": _estimate_max_tokens(medium_max_chars, minimum=128),
            "context_limit": 4,
        }

    return {
        "style": "long",
        "instruction": f"这轮可以回 2-3 句，但仍要克制，60-{long_max_chars} 个汉字左右，最多不超过 {long_max_chars} 个汉字。",
        "max_chars": long_max_chars,
        "max_tokens": _estimate_max_tokens(long_max_chars, minimum=192),
        "context_limit": 5,
    }


def _merge_response_preferences(response_preferences: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    defaults = {
        "ultra_short_max_chars": 30,
        "short_max_chars": 55,
        "medium_max_chars": 90,
        "long_max_chars": 140,
    }
    if not response_preferences:
        return defaults

    merged = dict(defaults)
    for key, default_value in defaults.items():
        raw = response_preferences.get(key, default_value)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default_value
        merged[key] = max(12, min(240, value))

    merged["short_max_chars"] = max(merged["short_max_chars"], merged["ultra_short_max_chars"])
    merged["medium_max_chars"] = max(merged["medium_max_chars"], merged["short_max_chars"])
    merged["long_max_chars"] = max(merged["long_max_chars"], merged["medium_max_chars"])
    return merged


def _estimate_max_tokens(max_chars: int, minimum: int) -> int:
    return max(minimum, int(max_chars * 1.6))


def summarize_recent_agent_replies(messages: Iterable[str], limit: int = 3) -> List[str]:
    """提取最近几条有意义的 Agent 回复，用于约束重复表达。"""
    summaries: List[str] = []

    for message in messages:
        cleaned = sanitize_input(message)
        if len(cleaned) < 4:
            continue

        normalized = _normalize_similarity_text(cleaned)
        if len(normalized) < 4:
            continue

        if any(_is_text_similar(normalized, _normalize_similarity_text(item)) for item in summaries):
            continue

        summaries.append(cleaned[:60])
        if len(summaries) >= limit:
            break

    return summaries


def is_response_too_similar(candidate: str, recent_replies: Iterable[str]) -> bool:
    """判断候选回复是否与最近回复过于相似。"""
    cleaned_candidate = sanitize_input(candidate)
    if not cleaned_candidate:
        return False

    normalized_candidate = _normalize_similarity_text(cleaned_candidate)
    if len(normalized_candidate) < 4:
        return False

    for recent in recent_replies:
        cleaned_recent = sanitize_input(recent)
        if not cleaned_recent:
            continue

        normalized_recent = _normalize_similarity_text(cleaned_recent)
        if len(normalized_recent) < 4:
            continue

        if _is_text_similar(normalized_candidate, normalized_recent):
            return True

    return False


def choose_natural_fallback_reply(user_message: str, user_emotion: Dict[str, float]) -> str:
    """根据用户输入和情绪选择自然的人设兜底文案。"""
    cleaned = sanitize_input(user_message)
    lowered = cleaned.lower()

    caring_markers = ("累", "烦", "难过", "焦虑", "压力", "困", "崩溃", "不舒服", "委屈", "难受", "加班")
    romantic_markers = ("想你", "爱你", "亲亲", "抱抱", "宝贝", "晚安", "早安")

    if any(marker in lowered for marker in caring_markers):
        return "我在呢[抱抱]，你继续说，我认真听着。"

    if any(marker in lowered for marker in romantic_markers):
        return "我在呀[心]，你再多和我说一点。"

    if user_emotion:
        caring_score = max(
            user_emotion.get("sadness", 0.0),
            user_emotion.get("anxiety", 0.0),
            user_emotion.get("tired", 0.0),
            user_emotion.get("stress", 0.0),
        )
        romantic_score = user_emotion.get("love", 0.0)

        if caring_score >= 0.3:
            return "我在呢[抱抱]，你继续说，我认真听着。"
        if romantic_score >= 0.3:
            return "我在呀[心]，你再多和我说一点。"

    return "我在呢，你接着说，我有在听。"


def _normalize_similarity_text(text: str) -> str:
    """归一化文本，便于做轻量相似度判断。"""
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text).lower()


def _shared_prefix(left: str, right: str) -> int:
    """返回两个字符串的公共前缀长度。"""
    size = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        size += 1
    return size


def _is_text_similar(left: str, right: str) -> bool:
    """轻量判断两段文本是否属于高重复表达。"""
    if left == right:
        return True

    if _shared_prefix(left, right) >= 6:
        return True

    overlap = len(set(left) & set(right)) / max(1, min(len(set(left)), len(set(right))))
    if min(len(left), len(right)) >= 8 and overlap >= 0.7:
        return True

    return SequenceMatcher(None, left, right).ratio() >= 0.82
