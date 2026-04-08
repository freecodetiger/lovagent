import asyncio
from datetime import datetime, timedelta
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.models.database import SessionLocal, init_db
from app.models.user import InboundAggregateBatch, InboundMessageEvent, User
from app.services.incoming_aggregation_service import incoming_aggregation_service


class IncomingAggregationServiceTests(unittest.TestCase):
    def setUp(self):
        init_db()
        suffix = uuid4().hex[:8]
        self.wecom_user_id = f"agg-user-{suffix}"

    def tearDown(self):
        db = SessionLocal()
        try:
            db.query(InboundMessageEvent).filter(InboundMessageEvent.wecom_user_id == self.wecom_user_id).delete(
                synchronize_session=False
            )
            db.query(InboundAggregateBatch).filter(InboundAggregateBatch.wecom_user_id == self.wecom_user_id).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.wecom_user_id == self.wecom_user_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _text_message(self, msg_id: str, content: str) -> dict:
        return {
            "msg_id": msg_id,
            "from_user": self.wecom_user_id,
            "create_time": str(datetime.now().timestamp()),
            "msg_type": "text",
            "content": content,
        }

    def _image_message(self, msg_id: str) -> dict:
        return {
            "msg_id": msg_id,
            "from_user": self.wecom_user_id,
            "create_time": str(datetime.now().timestamp()),
            "msg_type": "image",
            "media_id": f"media-{msg_id}",
            "image_url": "https://example.com/demo.jpg",
        }

    def _pdf_message(self, msg_id: str, file_name: str = "note.pdf") -> dict:
        return {
            "msg_id": msg_id,
            "from_user": self.wecom_user_id,
            "create_time": str(datetime.now().timestamp()),
            "msg_type": "file",
            "media_id": f"media-{msg_id}",
            "file_name": file_name,
        }

    def _expire_batch(self, batch_id: int) -> None:
        db = SessionLocal()
        try:
            batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == batch_id).first()
            batch.window_expires_at = datetime.now() - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

    def test_register_event_is_idempotent_for_same_msg_id(self):
        first = asyncio.run(incoming_aggregation_service.register_event(self._text_message("dup-1", "你好")))
        second = asyncio.run(incoming_aggregation_service.register_event(self._text_message("dup-1", "你好")))

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["batch_id"], second["batch_id"])

        db = SessionLocal()
        try:
            event_count = db.query(InboundMessageEvent).filter(InboundMessageEvent.wecom_user_id == self.wecom_user_id).count()
            batch_count = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.wecom_user_id == self.wecom_user_id).count()
        finally:
            db.close()

        self.assertEqual(event_count, 1)
        self.assertEqual(batch_count, 1)

    def test_register_event_merges_messages_into_same_open_batch(self):
        first = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-1", "第一句")))
        second = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-2", "第二句")))

        self.assertEqual(first["batch_id"], second["batch_id"])

        db = SessionLocal()
        try:
            batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == first["batch_id"]).first()
            events = (
                db.query(InboundMessageEvent)
                .filter(InboundMessageEvent.batch_id == first["batch_id"])
                .order_by(InboundMessageEvent.id.asc())
                .all()
            )
        finally:
            db.close()

        self.assertEqual(len(events), 2)
        self.assertGreater(batch.window_expires_at, batch.window_started_at)

    def test_register_event_creates_new_batch_after_window_expires(self):
        first = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-1", "第一句")))
        self._expire_batch(first["batch_id"])

        second = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-2", "第二句")))

        self.assertNotEqual(first["batch_id"], second["batch_id"])

    def test_process_ready_batch_merges_text_messages_into_single_graph_input(self):
        first = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-1", "今天有点累")))
        asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-2", "刚开完会")))
        self._expire_batch(first["batch_id"])

        graph_mock = AsyncMock(return_value={"agent_response": "抱抱你"})
        with patch("app.services.incoming_aggregation_service.run_incoming_message_graph", graph_mock):
            processed = asyncio.run(incoming_aggregation_service.process_ready_batch(first["batch_id"]))

        self.assertTrue(processed)
        graph_mock.assert_awaited_once_with(
            {
                "user_id": self.wecom_user_id,
                "user_content": "今天有点累\n刚开完会",
            }
        )

        db = SessionLocal()
        try:
            batch = db.query(InboundAggregateBatch).filter(InboundAggregateBatch.id == first["batch_id"]).first()
            processed_count = (
                db.query(InboundMessageEvent)
                .filter(
                    InboundMessageEvent.batch_id == first["batch_id"],
                    InboundMessageEvent.processed.is_(True),
                )
                .count()
            )
        finally:
            db.close()

        self.assertEqual(batch.status, "completed")
        self.assertEqual(processed_count, 2)

    def test_process_ready_batch_routes_mixed_batch_to_multimodal_service(self):
        first = asyncio.run(incoming_aggregation_service.register_event(self._text_message("msg-1", "你看看这个")))
        asyncio.run(incoming_aggregation_service.register_event(self._image_message("msg-2")))
        asyncio.run(incoming_aggregation_service.register_event(self._pdf_message("msg-3", "report.pdf")))
        self._expire_batch(first["batch_id"])

        multimodal_mock = AsyncMock(return_value={"reply": "我看完啦"})
        with patch.object(
            incoming_aggregation_service,
            "schedule_user_processing",
        ), patch(
            "app.services.incoming_aggregation_service.multimodal_chat_service.process_aggregated_input",
            multimodal_mock,
        ):
            processed = asyncio.run(incoming_aggregation_service.process_ready_batch(first["batch_id"]))

        self.assertTrue(processed)
        multimodal_mock.assert_awaited_once()
        kwargs = multimodal_mock.await_args.kwargs
        self.assertEqual(kwargs["user_id"], self.wecom_user_id)
        self.assertEqual(kwargs["user_message"], "你看看这个\n[图片] 用户发送了一张图片\n[PDF] 用户发送了文件《report.pdf》")
        self.assertEqual(len(kwargs["attachments"]), 2)
        self.assertEqual(kwargs["attachments"][0]["msg_type"], "image")
        self.assertEqual(kwargs["attachments"][1]["file_name"], "report.pdf")


if __name__ == "__main__":
    unittest.main()
