"""
Conversation persistence executors.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.services.memory_service import memory_service


async def save_conversation(
    *,
    channel: str,
    external_user_id: str,
    user_message: str,
    agent_message: str,
    user_emotion: Dict,
    agent_emotion: Dict,
    memories_used: Optional[Dict] = None,
) -> Optional[int]:
    return await memory_service.save_conversation(
        channel=channel,
        external_user_id=external_user_id,
        user_message=user_message,
        agent_message=agent_message,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
        memories_used=memories_used,
    )


def schedule_memory_processing(
    *,
    channel: str,
    external_user_id: str,
    conversation_id: Optional[int],
    user_message: str,
    agent_message: str,
    user_emotion: Dict,
    agent_emotion: Dict,
) -> None:
    memory_service.schedule_memory_processing(
        channel=channel,
        external_user_id=external_user_id,
        conversation_id=conversation_id,
        user_message=user_message,
        agent_message=agent_message,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
    )
