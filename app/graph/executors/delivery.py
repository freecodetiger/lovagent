"""
Delivery executors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from app.models.admin import ProactiveChatLog
from app.models.database import SessionLocal
from app.models.user import Conversation, User
from app.services.wecom_service import wecom_service


async def deliver_incoming_reply(*, to_user: str, content: str) -> Dict[str, object]:
    delivery_result: Dict[str, object] = {"attempted": True, "status": "sent"}
    try:
        await wecom_service.send_text_message(to_user, content)
    except Exception as exc:
        print(f"发送企业微信消息失败: {exc}")
        delivery_result = {"attempted": True, "status": "failed", "error_message": str(exc)}
    return delivery_result


async def deliver_proactive_outreach(
    *,
    target_wecom_user_id: str,
    trigger_type: str,
    window_key: Optional[str],
    content: str,
) -> Dict[str, object]:
    sent_at = datetime.now()
    status = "failed"
    error_message = None

    try:
        await wecom_service.send_text_message(target_wecom_user_id, content)
        status = "sent"
        _save_proactive_conversation(target_wecom_user_id=target_wecom_user_id, content=content, sent_at=sent_at)
    except Exception as exc:
        error_message = str(exc)
        print(f"主动聊天发送失败: {exc}")
    finally:
        _save_proactive_log(
            target_wecom_user_id=target_wecom_user_id,
            trigger_type=trigger_type,
            window_key=window_key,
            content=content,
            status=status,
            error_message=error_message,
            sent_at=sent_at,
        )

    return {
        "attempted": True,
        "status": status,
        "error_message": error_message,
        "sent_at": sent_at.isoformat(),
    }


def _save_proactive_conversation(*, target_wecom_user_id: str, content: str, sent_at: datetime) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.wecom_user_id == target_wecom_user_id).first()
        if not user:
            return

        conversation = Conversation(
            user_id=user.id,
            user_message="",
            agent_message=content,
            user_emotion=None,
            agent_emotion="happy",
            agent_emotion_intensity=40,
            context_used=True,
            memories_used={"source": "proactive"},
            created_at=sent_at,
        )
        db.add(conversation)
        db.commit()
    finally:
        db.close()


def _save_proactive_log(
    *,
    target_wecom_user_id: str,
    trigger_type: str,
    window_key: Optional[str],
    content: str,
    status: str,
    error_message: Optional[str],
    sent_at: datetime,
) -> None:
    db = SessionLocal()
    try:
        log = ProactiveChatLog(
            target_wecom_user_id=target_wecom_user_id,
            trigger_type=trigger_type,
            window_key=window_key,
            content=content,
            status=status,
            error_message=error_message,
            sent_at=sent_at,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
