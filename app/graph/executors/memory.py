"""
Memory persistence executors.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.models.database import SessionLocal
from app.models.user import Conversation
from app.services.memory_service import memory_service


async def load_memory_update_context(channel: str, external_user_id: str) -> Tuple[Dict, List[Dict[str, str]]]:
    db = SessionLocal()
    try:
        user = memory_service._get_user_by_channel_external_id(db, channel, external_user_id)
        if not user:
            return {}, []

        short_term = memory_service._get_or_create_short_term_memory(db, user.id)
        recent_messages = memory_service._serialize_llm_messages(
            memory_service._get_recent_conversations_rows(
                db,
                user.id,
                limit=max(3, memory_service.max_short_term_messages // 2),
            )
        )
        existing_memory = memory_service._build_profile_snapshot(
            user,
            short_term_memory=memory_service._serialize_short_term_memory(short_term),
            memory_items=[],
        )
        return existing_memory, recent_messages
    finally:
        db.close()


async def persist_memory_update(
    *,
    channel: str,
    external_user_id: str,
    conversation_id: int,
    user_message: str,
    agent_message: str,
    user_emotion: Dict,
    extracted: Dict[str, object],
) -> None:
    db = SessionLocal()
    try:
        user = memory_service._get_user_by_channel_external_id(db, channel, external_user_id)
        if not user:
            return

        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return

        short_term = memory_service._get_or_create_short_term_memory(db, user.id)
        memory_service._apply_long_term_updates(user, extracted)
        memory_service._upsert_memory_items(
            db=db,
            user=user,
            conversation_id=conversation_id,
            extracted=extracted,
        )
        memory_service._update_short_term_memory(
            short_term=short_term,
            user_message=user_message,
            agent_message=agent_message,
            user_emotion=user_emotion,
            extracted=extracted,
        )
        conversation.memories_used = {
            **(conversation.memories_used or {}),
            "source": (conversation.memories_used or {}).get("source", "reply"),
            "memory_pipeline": "langgraph",
        }
        db.commit()
    finally:
        db.close()
