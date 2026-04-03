"""
工具函数模块
"""

from datetime import datetime
from typing import Optional


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