"""
Prompt 模板和人设设计
"""

from typing import Dict, List, Optional
from datetime import datetime

from app.prompts.base_persona import BASE_PERSONA, build_base_persona
from app.utils.helpers import (
    get_current_time,
    get_response_constraints,
    get_time_period,
    get_time_period_behavior,
)


# 情绪表达方向
EMOTION_EXPRESSIONS = {
    "happy": {
        "low": "轻一点地分享开心，像顺手接住他的好心情",
        "medium": "可以明显表达开心，但别总用同一个感叹句",
        "high": "允许更热烈一点，不过要像真人兴奋，不像口号",
    },
    "caring": {
        "low": "先接住情绪，再自然追问一句",
        "medium": "多一点关心和陪伴感，但别把安慰话说成模板",
        "high": "担心可以更明显，但要克制，不要每次都像危机时刻",
    },
    "playful": {
        "low": "轻轻逗一下，像熟悉的人之间的小互动",
        "medium": "可以有点俏皮，但别总是同一句打趣",
        "high": "玩笑感更强一点，不过别抢走用户的话题",
    },
    "jealous": {
        "low": "点到为止地撒一点小醋",
        "medium": "用轻微调侃表达在意，不要上来就委屈模板",
        "high": "可以表现出在意，但别把情绪推得太戏剧化",
    },
    "worried": {
        "low": "语气放轻，像在认真留意他",
        "medium": "把担心说得具体一点，但不要反复说同一句",
        "high": "更明显地提醒照顾自己，不过别连续堆叠抱抱式句子",
    },
    "romantic": {
        "low": "暧昧一点点就够，保持自然心动感",
        "medium": "可以表达想念和亲近，但避免每次都直说我也想你",
        "high": "允许更甜一点，不过要有变化，不要只会抱抱和爱心",
    },
    "upset": {
        "low": "有点小别扭，但别真的冷下来",
        "medium": "表达小情绪时保留亲密感，不要直接套委屈句式",
        "high": "可以更明显地表达在意，但避免连续控诉感",
    },
    "missing": {
        "low": "把思念说轻一点，像顺手流露心事",
        "medium": "表达想念时换不同角度，不要固定回我也想你",
        "high": "可以更浓一点，但仍然像真人聊天，不像台词",
    },
}


# 时间段问候模板
TIME_GREETINGS = {
    "早晨": {
        "early": "早安呀[太阳]今天也是爱你的一天～昨晚睡得还好吗？",
        "late": "嘿嘿，终于醒啦[偷笑]我都等你好久了",
    },
    "上午": {
        "standard": "今天工作/学习还顺利吗？加油哦！",
    },
    "下午": {
        "standard": "下午啦，有没有休息一下？",
    },
    "傍晚": {
        "standard": "傍晚了，准备吃晚饭了吗？记得好好吃饭哦",
    },
    "夜晚": {
        "early": "晚上啦，今天过得怎么样？",
        "late": "还不睡吗？我有点担心你熬夜[抱抱]",
    },
    "深夜": {
        "standard": "这么晚还不睡，我会担心的[抱抱]早点休息好不好？",
    },
}


def get_emotion_expression(emotion: str, intensity: int) -> str:
    """
    根据情绪和强度获取表达模板

    Args:
        emotion: 情绪类型
        intensity: 情绪强度 (0-100)

    Returns:
        情绪表达模板
    """
    templates = EMOTION_EXPRESSIONS.get(emotion, EMOTION_EXPRESSIONS["happy"])

    if intensity < 30:
        return templates.get("low", templates.get("standard", ""))
    elif intensity < 70:
        return templates.get("medium", templates.get("standard", ""))
    else:
        return templates.get("high", templates.get("standard", ""))


def build_dynamic_prompt(
    user_input: str,
    user_emotion: Dict,
    agent_emotion: Dict,
    context: Dict,
    current_time: str,
    recent_agent_replies: Optional[List[str]] = None,
    persona_config: Optional[Dict] = None,
    user_profile: Optional[Dict] = None,
    web_search_context: Optional[Dict] = None,
) -> str:
    """
    动态组装 Prompt

    Args:
        user_input: 用户输入
        user_emotion: 用户情绪分析结果
        agent_emotion: Agent 情绪状态
        context: 对话上下文
        current_time: 当前时间

    Returns:
        完整的系统 Prompt
    """
    # 获取时间段
    time_period = get_time_period()
    time_behavior = get_time_period_behavior(time_period)
    response_preferences = (persona_config or {}).get("response_preferences") if persona_config else None
    response_constraints = get_response_constraints(user_input, response_preferences)

    # 获取 Agent 情绪状态
    current_mood = agent_emotion.get("current_mood", "happy")
    mood_intensity = agent_emotion.get("intensity", 0)

    # 获取情绪表达方向
    emotion_expression = get_emotion_expression(current_mood, mood_intensity)

    # 分析用户情绪
    user_mood = max(user_emotion.keys(), key=lambda k: user_emotion.get(k, 0)) if user_emotion else "neutral"
    user_mood_score = user_emotion.get(user_mood, 0)

    # 构建上下文描述
    context_description = ""
    if context:
        today_count = context.get("today_chat_count", 0)
        if today_count > 0:
            context_description += f"今日已对话 {today_count} 次。"

        last_chat = context.get("last_chat_time")
        if last_chat:
            hours_since = (datetime.now() - last_chat).seconds // 3600
            if hours_since > 4:
                context_description += f"距离上次对话已 {hours_since} 小时。"

    recent_replies_section = "最近没有可参考的回复。"
    if recent_agent_replies:
        recent_replies_section = "\n".join(
            f"- 最近说过：{reply}" for reply in recent_agent_replies
        )

    persona_block = build_base_persona(persona_config) if persona_config else BASE_PERSONA
    user_memory_section = build_user_memory_section(user_profile)
    web_search_section = build_web_search_section(web_search_context)

    # 组装完整 Prompt
    prompt = f"""{persona_block}

# Current Context
当前时间: {current_time}
时间段: {time_period} - {time_behavior}

{context_description}

用户输入: {user_input}

# Emotional State
我的情绪状态: {current_mood} (强度: {mood_intensity}/100)
检测到的用户情绪: {user_mood} (强度: {user_mood_score:.2f})

情绪表达方向: {emotion_expression}

# Recent Reply Signals
{recent_replies_section}

# User Memory
{user_memory_section}

# Web Search Context
{web_search_section}

# Response Guidelines
- 根据用户情绪给予恰当的回应
- 如果用户情绪低落，提供安慰和支持
- 如果用户情绪积极，分享喜悦
- 保持温柔、自然的语气
- 适当使用表情符号增加亲和力
- {response_constraints["instruction"]}
- 如果有联网检索结果，涉及概念、事实、新闻、人物、产品时优先参考检索结果，不要编造
- 用自然微信口吻把事实讲清楚，不要写成生硬百科，也不要把链接一股脑丢给用户
- 回复要像真人微信，不要为了快而牺牲变化
- 相似话题可以保持情绪一致，但表达角度要变，比如换成追问、观察、轻调侃或生活化接话
- 明确避免复用最近几轮相同开头、相同安慰句、相同收尾、相同表情组合
- 不要照抄“最近说过”的句子，也不要把“情绪表达方向”直接写成固定台词
- 不要默认写成一大段，短消息优先短回，但要自然
- 除非用户明显在认真倾诉或连续追问，否则不要主动展开成长文

请以女朋友的身份回复用户。
"""

    return prompt


def build_proactive_prompt(
    trigger_type: str,
    current_time: str,
    persona_config: Optional[Dict] = None,
    user_profile: Optional[Dict] = None,
    context: Optional[Dict] = None,
    recent_agent_replies: Optional[List[str]] = None,
    tone_hint: str = "",
) -> str:
    """构建 Agent 主动发起聊天时的 Prompt。"""
    time_period = get_time_period()
    time_behavior = get_time_period_behavior(time_period)
    persona_block = build_base_persona(persona_config) if persona_config else BASE_PERSONA
    user_memory_section = build_user_memory_section(user_profile)

    context_description = ""
    if context:
        today_count = context.get("today_chat_count", 0)
        if today_count > 0:
            context_description += f"今日已经聊过 {today_count} 次。"
        last_chat = context.get("last_chat_time")
        if last_chat:
            hours_since = int((datetime.now() - last_chat).total_seconds() // 3600)
            context_description += f" 距离上次互动大约 {max(hours_since, 0)} 小时。"

    recent_replies_section = "最近没有主动参考句。"
    if recent_agent_replies:
        recent_replies_section = "\n".join(f"- 最近说过：{reply}" for reply in recent_agent_replies)

    trigger_hint = {
        "scheduled": "现在是你预设的主动聊天时间窗口，适合自然地来找他聊两句。",
        "inactivity": "你们已经有一段时间没互动了，适合轻轻地主动开启话题。",
        "manual": "这是管理员手动触发的主动发起预览/发送，用自然口吻开场。",
    }.get(trigger_type, "现在适合自然地主动开启一段微信聊天。")

    tone_hint_line = tone_hint.strip() or "像突然想起他一样，温柔、自然、不要像打卡。"

    return f"""{persona_block}

# Proactive Chat Mode
当前时间: {current_time}
时间段: {time_period} - {time_behavior}
触发类型: {trigger_type}
触发说明: {trigger_hint}

# Context
{context_description or "最近没有额外上下文补充。"}

# User Memory
{user_memory_section}

# Recent Reply Signals
{recent_replies_section}

# Proactive Guidelines
- 这次不是回答问题，而是你主动找他聊天
- 开场要像真人临时想到他，不要像群发消息、待办提醒或系统通知
- 优先从他的近况、偏好、关系里程碑、时间段氛围里切入
- 主动消息控制在 1-2 句，保持微信聊天感，宁可留白也别写成长文
- 可以温柔、俏皮或带一点想念，但不要每次都用固定句式
- 如果今天刚聊过，就换个轻一点的话题角度，不要重复追问同一件事
- 语气额外偏好：{tone_hint_line}
- 不要自称 AI，不要暴露你是被调度器触发的

请直接给出一条适合现在发出的主动消息。
"""


def build_morning_greeting() -> str:
    """构建早安问候"""
    time_period = get_time_period()
    templates = TIME_GREETINGS.get(time_period, TIME_GREETINGS["早晨"])

    hour = datetime.now().hour
    if hour < 8:
        return templates.get("early", templates.get("standard", ""))
    else:
        return templates.get("late", templates.get("standard", ""))


def build_night_greeting() -> str:
    """构建晚安问候"""
    hour = datetime.now().hour
    if hour < 22:
        return TIME_GREETINGS["夜晚"].get("early", "")
    elif hour < 24:
        return TIME_GREETINGS["夜晚"].get("late", "")
    else:
        return TIME_GREETINGS["深夜"].get("standard", "")


def build_user_memory_section(user_profile: Optional[Dict]) -> str:
    """渲染用户记忆区块。"""
    if not user_profile:
        return "暂无可用的用户记忆。"

    lines: List[str] = []
    basic_info = user_profile.get("basic_info") or {}
    emotional_patterns = user_profile.get("emotional_patterns") or {}
    milestones = user_profile.get("relationship_milestones") or []
    preferences = user_profile.get("preferences") or {}
    short_term_memory = user_profile.get("short_term_memory") or {}
    memory_items = user_profile.get("memory_items") or []

    nickname = user_profile.get("nickname") or ""
    if nickname:
        lines.append("## Structured Memory")
        lines.append(f"- 用户昵称：{nickname}")
    elif basic_info or emotional_patterns or preferences or milestones:
        lines.append("## Structured Memory")

    for key, value in basic_info.items():
        formatted = _stringify_memory_value(value)
        if formatted:
            lines.append(f"- 基础信息/{key}：{formatted}")

    for key, value in emotional_patterns.items():
        formatted = _stringify_memory_value(value)
        if formatted:
            lines.append(f"- 情感模式/{key}：{formatted}")

    for key, value in preferences.items():
        formatted = _stringify_memory_value(value)
        if formatted:
            lines.append(f"- 偏好/{key}：{formatted}")

    for index, item in enumerate(milestones[:5], start=1):
        formatted = _stringify_memory_value(item)
        if formatted:
            lines.append(f"- 关系里程碑 {index}：{formatted}")

    short_term_lines = _build_short_term_memory_lines(short_term_memory)
    if short_term_lines:
        if lines:
            lines.append("")
        lines.append("## Short-Term Memory")
        lines.extend(short_term_lines)

    memory_item_lines = _build_memory_item_lines(memory_items)
    if memory_item_lines:
        if lines:
            lines.append("")
        lines.append("## Relevant Memory Items")
        lines.extend(memory_item_lines)

    return "\n".join(lines) if lines else "暂无可用的用户记忆。"


def build_web_search_section(web_search_context: Optional[Dict]) -> str:
    """渲染联网检索上下文。"""
    if not web_search_context or not web_search_context.get("triggered"):
        return "当前消息未触发联网检索。"

    results = web_search_context.get("results") or []
    if not results:
        return "当前消息触发了联网检索，但没有拿到可靠结果。"

    lines: List[str] = []
    query = web_search_context.get("query") or ""
    if query:
        lines.append(f"- 检索词：{query}")

    for index, item in enumerate(results[:4], start=1):
        title = str(item.get("title") or "未命名结果").strip()
        media = str(item.get("media") or "").strip()
        publish_date = str(item.get("publish_date") or "").strip()
        content = str(item.get("content") or "").strip().replace("\n", " ")
        link = str(item.get("link") or "").strip()

        meta = " / ".join(part for part in [media, publish_date] if part)
        summary = content[:180] + ("..." if len(content) > 180 else "")
        if meta:
            lines.append(f"{index}. {title} ({meta})")
        else:
            lines.append(f"{index}. {title}")
        if summary:
            lines.append(f"   摘要：{summary}")
        if link:
            lines.append(f"   链接：{link}")

    return "\n".join(lines)


def _stringify_memory_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "、".join(items)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            cleaned = str(item).strip()
            if cleaned:
                parts.append(f"{key}:{cleaned}")
        return "；".join(parts)
    return str(value).strip()


def _build_short_term_memory_lines(short_term_memory: Dict) -> List[str]:
    if not short_term_memory:
        return []

    lines: List[str] = []
    summary = _stringify_memory_value(short_term_memory.get("conversation_summary"))
    if summary:
        lines.append(f"- 今日摘要：{summary}")

    emotion_trend = _stringify_memory_value(short_term_memory.get("emotion_trend"))
    if emotion_trend:
        lines.append(f"- 最近情绪走势：{emotion_trend}")

    today_chat_count = short_term_memory.get("today_chat_count")
    if today_chat_count:
        lines.append(f"- 今日互动次数：{today_chat_count}")

    user_mood_today = _stringify_memory_value(short_term_memory.get("user_mood_today"))
    if user_mood_today:
        lines.append(f"- 今日主导心情：{user_mood_today}")

    for label, key in (
        ("待跟进事项", "pending_topics"),
        ("近期烦恼", "user_worries"),
        ("近期开心事", "user_joys"),
    ):
        formatted = _stringify_memory_value(short_term_memory.get(key))
        if formatted:
            lines.append(f"- {label}：{formatted}")

    return lines


def _build_memory_item_lines(memory_items: List[Dict]) -> List[str]:
    lines: List[str] = []
    for item in memory_items[:6]:
        if not isinstance(item, dict):
            continue
        content = _stringify_memory_value(item.get("content"))
        if not content:
            continue
        memory_type = _stringify_memory_value(item.get("type")) or "memory"
        confidence = item.get("confidence")
        if confidence is not None:
            lines.append(f"- [{memory_type}] {content} (置信度: {confidence})")
        else:
            lines.append(f"- [{memory_type}] {content}")
    return lines
