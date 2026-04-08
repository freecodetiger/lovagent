"""
企业微信入站消息幂等与聚合服务。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
import hashlib
from typing import Dict, List

from app.graph import run_incoming_message_graph
from app.models.database import SessionLocal
from app.models.user import InboundAggregateBatch, InboundMessageEvent
from app.services.multimodal_chat_service import multimodal_chat_service


MERGE_WINDOW_SECONDS = 5
logger = logging.getLogger(__name__)


class IncomingAggregationService:
    """对企业微信入站消息做幂等去重与短时聚合。"""

    def __init__(self) -> None:
        self._user_tasks: Dict[str, asyncio.Task] = {}
        self._background_tasks: set[asyncio.Task] = set()

    async def register_event(self, message: Dict[str, object]) -> Dict[str, object]:
        """登记入站消息事件，并绑定到一个聚合批次。"""
        user_id = str(message.get("from_user") or "").strip()
        if not user_id:
            raise ValueError("Missing from_user")

        msg_id = self._resolve_message_key(message)
        now = datetime.now()
        window_expires_at = now + timedelta(seconds=MERGE_WINDOW_SECONDS)

        db = SessionLocal()
        try:
            existing = db.query(InboundMessageEvent).filter(InboundMessageEvent.msg_id == msg_id).first()
            if existing:
                return {
                    "duplicate": True,
                    "msg_id": msg_id,
                    "user_id": existing.wecom_user_id,
                    "batch_id": existing.batch_id,
                }

            batch = self._get_open_batch(db, user_id, now)
            if batch is None:
                batch = InboundAggregateBatch(
                    wecom_user_id=user_id,
                    status="collecting",
                    window_started_at=now,
                    window_expires_at=window_expires_at,
                    last_event_at=now,
                )
                db.add(batch)
                db.flush()
            else:
                batch.last_event_at = now
                batch.window_expires_at = window_expires_at

            event = InboundMessageEvent(
                msg_id=msg_id,
                batch_id=batch.id,
                wecom_user_id=user_id,
                msg_type=str(message.get("msg_type") or "").strip().lower() or "text",
                content_text=self._normalize_event_text(message),
                media_id=str(message.get("media_id") or "").strip() or None,
                file_name=str(message.get("file_name") or message.get("title") or "").strip() or None,
                image_url=str(message.get("image_url") or "").strip() or None,
                processed=False,
            )
            db.add(event)
            db.commit()
            return {
                "duplicate": False,
                "msg_id": msg_id,
                "user_id": user_id,
                "batch_id": batch.id,
            }
        finally:
            db.close()

    def schedule_user_processing(self, user_id: str) -> None:
        """为某个用户调度后台聚合处理任务。"""
        cleaned_user_id = str(user_id).strip()
        if not cleaned_user_id:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        current = self._user_tasks.get(cleaned_user_id)
        if current and not current.done():
            return

        task = loop.create_task(self._run_user_loop(cleaned_user_id))
        self._user_tasks[cleaned_user_id] = task
        self._background_tasks.add(task)
        task.add_done_callback(lambda done: self._on_task_done(cleaned_user_id, done))

    async def process_ready_batch(self, batch_id: int) -> bool:
        """处理一个已经达到静默窗口的聚合批次。"""
        if not batch_id:
            return False

        now = datetime.now()
        db = SessionLocal()
        try:
            batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == batch_id).first()
            if batch is None or batch.status != "collecting":
                return False
            if batch.window_expires_at and batch.window_expires_at > now:
                return False

            batch.status = "processing"
            db.commit()

            events = (
                db.query(InboundMessageEvent)
                .filter(InboundMessageEvent.batch_id == batch_id)
                .order_by(InboundMessageEvent.created_at.asc(), InboundMessageEvent.id.asc())
                .all()
            )
            if not events:
                batch.status = "completed"
                batch.reply_sent_at = now
                db.commit()
                return True
        finally:
            db.close()

        user_id = events[0].wecom_user_id
        user_message = self._build_merged_user_message(events)
        attachments = self._build_attachment_list(events)

        try:
            if attachments:
                await multimodal_chat_service.process_aggregated_input(
                    user_id=user_id,
                    user_message=user_message,
                    attachments=attachments,
                )
            else:
                await run_incoming_message_graph(
                    {
                        "user_id": user_id,
                        "user_content": user_message,
                    }
                )
        except Exception:
            db = SessionLocal()
            try:
                batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == batch_id).first()
                if batch:
                    batch.status = "collecting"
                db.commit()
            finally:
                db.close()
            raise

        db = SessionLocal()
        try:
            batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == batch_id).first()
            if batch:
                batch.status = "completed"
                batch.reply_sent_at = datetime.now()

            (
                db.query(InboundMessageEvent)
                .filter(InboundMessageEvent.batch_id == batch_id)
                .update({"processed": True}, synchronize_session=False)
            )
            db.commit()
        finally:
            db.close()

        return True

    async def _run_user_loop(self, user_id: str) -> None:
        while True:
            batch = self._get_oldest_collecting_batch(user_id)
            if batch is None:
                return

            now = datetime.now()
            if batch.window_expires_at and batch.window_expires_at > now:
                await asyncio.sleep(max((batch.window_expires_at - now).total_seconds(), 0.05))

            processed = await self.process_ready_batch(batch.id)
            if not processed:
                await asyncio.sleep(0.05)

    def _on_task_done(self, user_id: str, task: asyncio.Task) -> None:
        self._background_tasks.discard(task)
        current = self._user_tasks.get(user_id)
        if current is task:
            self._user_tasks.pop(user_id, None)
        try:
            task.result()
        except Exception as exc:
            logger.exception("入站消息聚合处理失败: user=%s", user_id)

    def _get_open_batch(self, db, user_id: str, now: datetime) -> InboundAggregateBatch | None:
        batch = (
            db.query(InboundAggregateBatch)
            .filter(
                InboundAggregateBatch.wecom_user_id == user_id,
                InboundAggregateBatch.status == "collecting",
            )
            .order_by(InboundAggregateBatch.created_at.desc(), InboundAggregateBatch.id.desc())
            .first()
        )
        if batch and batch.window_expires_at and batch.window_expires_at >= now:
            return batch
        return None

    def _get_oldest_collecting_batch(self, user_id: str) -> InboundAggregateBatch | None:
        db = SessionLocal()
        try:
            return (
                db.query(InboundAggregateBatch)
                .filter(
                    InboundAggregateBatch.wecom_user_id == user_id,
                    InboundAggregateBatch.status == "collecting",
                )
                .order_by(InboundAggregateBatch.window_started_at.asc(), InboundAggregateBatch.id.asc())
                .first()
            )
        finally:
            db.close()

    def _resolve_message_key(self, message: Dict[str, object]) -> str:
        msg_id = str(message.get("msg_id") or "").strip()
        if msg_id:
            return msg_id

        raw = "|".join(
            [
                str(message.get("from_user") or "").strip(),
                str(message.get("create_time") or "").strip(),
                str(message.get("msg_type") or "").strip(),
                str(message.get("content") or "").strip(),
                str(message.get("media_id") or "").strip(),
                str(message.get("file_name") or message.get("title") or "").strip(),
                str(message.get("image_url") or "").strip(),
            ]
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"synthetic:{digest}"

    def _normalize_event_text(self, message: Dict[str, object]) -> str:
        msg_type = str(message.get("msg_type") or "").strip().lower()
        if msg_type == "text":
            return str(message.get("content") or "").strip()
        if msg_type == "image":
            return "[图片] 用户发送了一张图片"
        if msg_type == "file":
            file_name = str(message.get("file_name") or message.get("title") or "未命名文件").strip() or "未命名文件"
            if file_name.lower().endswith(".pdf"):
                return f"[PDF] 用户发送了文件《{file_name}》"
            return f"[文件] 用户发送了文件《{file_name}》"
        return f"[{msg_type or '消息'}] 用户发送了一条消息"

    def _build_merged_user_message(self, events: List[InboundMessageEvent]) -> str:
        lines = [str(event.content_text or "").strip() for event in events if str(event.content_text or "").strip()]
        return "\n".join(lines) if lines else "用户发送了一条新消息"

    def _build_attachment_list(self, events: List[InboundMessageEvent]) -> List[Dict[str, object]]:
        attachments: List[Dict[str, object]] = []
        for event in events:
            msg_type = str(event.msg_type or "").strip().lower()
            if msg_type == "image":
                attachments.append(
                    {
                        "msg_type": "image",
                        "media_id": event.media_id,
                        "image_url": event.image_url,
                    }
                )
            elif msg_type == "file":
                file_name = str(event.file_name or "").strip()
                if file_name.lower().endswith(".pdf"):
                    attachments.append(
                        {
                            "msg_type": "file",
                            "media_id": event.media_id,
                            "file_name": file_name,
                        }
                    )
        return attachments


incoming_aggregation_service = IncomingAggregationService()
