"""
Proactive chat service.
"""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.exc import OperationalError

from app.config import settings
from app.models.admin import ProactiveChatConfig, ProactiveChatLog
from app.models.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)


DEFAULT_PROACTIVE_CHAT_CONFIG_KEY = "default_proactive_chat"
DEFAULT_SCHEDULED_WINDOWS = [
    {"key": "morning", "label": "上午", "enabled": True, "time": "09:30"},
    {"key": "afternoon", "label": "下午", "enabled": True, "time": "15:00"},
    {"key": "night", "label": "夜晚", "enabled": True, "time": "21:00"},
]
DEFAULT_QUIET_HOURS = {"enabled": True, "start": "23:00", "end": "09:00"}
DEFAULT_PROACTIVE_CHAT_CONFIG = {
    "enabled": False,
    "target_channel": "wecom",
    "target_external_user_id": "",
    "scheduled_windows": DEFAULT_SCHEDULED_WINDOWS,
    "inactivity_trigger_hours": 6,
    "quiet_hours": DEFAULT_QUIET_HOURS,
    "max_messages_per_day": 4,
    "min_interval_minutes": 180,
    "tone_hint": "像突然想起我一样，自然一点，别像打卡问候。",
}


class ProactiveChatService:
    """Proactive chat config, scheduling and dispatch."""

    def __init__(self):
        self.scheduler_interval_seconds = max(30, settings.proactive_scheduler_interval_seconds)

    def get_config(self) -> Dict:
        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(ProactiveChatConfig)
                    .filter(ProactiveChatConfig.config_key == DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                return self._build_payload(DEFAULT_PROACTIVE_CHAT_CONFIG)

            if not record:
                return self._build_payload(DEFAULT_PROACTIVE_CHAT_CONFIG)

            return self._build_payload(
                {
                    "enabled": record.enabled,
                    "target_channel": record.target_channel or "wecom",
                    "target_external_user_id": record.target_external_user_id or "",
                    "scheduled_windows": record.scheduled_windows or [],
                    "inactivity_trigger_hours": record.inactivity_trigger_hours,
                    "quiet_hours": record.quiet_hours or {},
                    "max_messages_per_day": record.max_messages_per_day,
                    "min_interval_minutes": record.min_interval_minutes,
                    "tone_hint": record.tone_hint or "",
                },
                updated_at=record.updated_at.isoformat() if record.updated_at else None,
            )
        finally:
            db.close()

    def save_config(self, config: Dict) -> Dict:
        normalized = self._normalize_config(config)
        db = SessionLocal()
        try:
            try:
                record = (
                    db.query(ProactiveChatConfig)
                    .filter(ProactiveChatConfig.config_key == DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
                    .first()
                )
            except OperationalError:
                db.rollback()
                record = None

            if not record:
                record = ProactiveChatConfig(config_key=DEFAULT_PROACTIVE_CHAT_CONFIG_KEY)
                db.add(record)

            record.enabled = normalized["enabled"]
            record.target_channel = normalized["target_channel"]
            record.target_external_user_id = normalized["target_external_user_id"] or None
            record.scheduled_windows = normalized["scheduled_windows"]
            record.inactivity_trigger_hours = normalized["inactivity_trigger_hours"]
            record.quiet_hours = normalized["quiet_hours"]
            record.max_messages_per_day = normalized["max_messages_per_day"]
            record.min_interval_minutes = normalized["min_interval_minutes"]
            record.tone_hint = normalized["tone_hint"]

            db.commit()
            db.refresh(record)
            return self.get_config()
        finally:
            db.close()

    async def preview_outreach(self, channel: Optional[str] = None, external_user_id: Optional[str] = None) -> Dict:
        target_channel, target_external_user_id = self._resolve_target_user(channel, external_user_id)
        from app.graph import run_proactive_chat_graph

        payload = await run_proactive_chat_graph(
            {
                "target_channel": target_channel,
                "target_external_user_id": target_external_user_id,
                "trigger_type": "manual",
                "window_key": None,
                "send_delivery": False,
            }
        )
        return self._format_graph_payload(payload)

    async def run_outreach_once(self, channel: Optional[str] = None, external_user_id: Optional[str] = None) -> Dict:
        target_channel, target_external_user_id = self._resolve_target_user(channel, external_user_id)
        from app.graph import run_proactive_chat_graph

        payload = await run_proactive_chat_graph(
            {
                "target_channel": target_channel,
                "target_external_user_id": target_external_user_id,
                "trigger_type": "manual",
                "window_key": None,
                "send_delivery": True,
            }
        )
        return self._format_graph_payload(payload)

    async def dispatch_due_messages(self) -> Optional[Dict]:
        config = self.get_config()
        due = self._resolve_due_trigger(config)
        if not due:
            return None

        from app.graph import run_proactive_chat_graph

        payload = await run_proactive_chat_graph(
            {
                "target_channel": config["target_channel"],
                "target_external_user_id": config["target_external_user_id"],
                "trigger_type": due["trigger_type"],
                "window_key": due.get("window_key"),
                "send_delivery": True,
            }
        )
        return self._format_graph_payload(payload)

    async def scheduler_loop(self) -> None:
        while True:
            try:
                result = await self.dispatch_due_messages()
                if result and result.get("delivery", {}).get("status") == "sent":
                    logger.info("主动聊天发送成功: %s:%s", result["target_channel"], result["target_external_user_id"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("主动聊天调度异常")

            await asyncio.sleep(self.scheduler_interval_seconds)

    def _build_payload(self, config: Dict, updated_at: Optional[str] = None) -> Dict:
        normalized = self._normalize_config(config)
        normalized["updated_at"] = updated_at
        normalized["target_wecom_user_id"] = (
            normalized["target_external_user_id"] if normalized["target_channel"] == "wecom" else ""
        )
        return normalized

    def _format_graph_payload(self, payload: Dict) -> Dict:
        return {
            "target_channel": payload["target_channel"],
            "target_external_user_id": payload["target_external_user_id"],
            "target_wecom_user_id": payload["target_external_user_id"] if payload["target_channel"] == "wecom" else "",
            "trigger_type": payload["trigger_type"],
            "window_key": payload.get("window_key"),
            "prompt": payload.get("prompt", ""),
            "reply": payload.get("reply", ""),
            "persona_config": payload.get("persona_config"),
            "user_memory": payload.get("user_memory"),
            "config": payload.get("proactive_config", self.get_config()),
            "delivery": payload.get("delivery", {"attempted": False, "status": "preview"}),
            "graph_trace": payload.get("graph_trace", []),
        }

    def _normalize_config(self, config: Optional[Dict]) -> Dict:
        merged = dict(DEFAULT_PROACTIVE_CHAT_CONFIG)
        if not config:
            merged["scheduled_windows"] = [dict(item) for item in DEFAULT_SCHEDULED_WINDOWS]
            merged["quiet_hours"] = dict(DEFAULT_QUIET_HOURS)
            return merged

        merged["enabled"] = bool(config.get("enabled", merged["enabled"]))
        legacy_target = str(config.get("target_wecom_user_id") or "").strip()
        merged["target_channel"] = str(config.get("target_channel") or "wecom").strip() or "wecom"
        merged["target_external_user_id"] = str(config.get("target_external_user_id") or legacy_target).strip()
        merged["scheduled_windows"] = self._normalize_scheduled_windows(config.get("scheduled_windows"))
        merged["quiet_hours"] = self._normalize_quiet_hours(config.get("quiet_hours"))
        merged["tone_hint"] = str(config.get("tone_hint") or merged["tone_hint"]).strip() or merged["tone_hint"]

        merged["inactivity_trigger_hours"] = self._coerce_int(
            config.get("inactivity_trigger_hours"),
            fallback=DEFAULT_PROACTIVE_CHAT_CONFIG["inactivity_trigger_hours"],
            minimum=1,
            maximum=168,
        )
        merged["max_messages_per_day"] = self._coerce_int(
            config.get("max_messages_per_day"),
            fallback=DEFAULT_PROACTIVE_CHAT_CONFIG["max_messages_per_day"],
            minimum=1,
            maximum=12,
        )
        merged["min_interval_minutes"] = self._coerce_int(
            config.get("min_interval_minutes"),
            fallback=DEFAULT_PROACTIVE_CHAT_CONFIG["min_interval_minutes"],
            minimum=10,
            maximum=1440,
        )
        return merged

    def _normalize_scheduled_windows(self, value: object) -> List[Dict]:
        items = value if isinstance(value, list) else DEFAULT_SCHEDULED_WINDOWS
        normalized: List[Dict] = []
        fallback_by_key = {item["key"]: item for item in DEFAULT_SCHEDULED_WINDOWS}

        for item in items:
            if not isinstance(item, dict):
                continue

            key = str(item.get("key") or "").strip()
            if not key:
                continue

            fallback = fallback_by_key.get(key, {"label": key, "time": "12:00", "enabled": True})
            normalized.append(
                {
                    "key": key,
                    "label": str(item.get("label") or fallback["label"]).strip() or fallback["label"],
                    "enabled": bool(item.get("enabled", fallback["enabled"])),
                    "time": self._normalize_clock_time(item.get("time"), fallback["time"]),
                }
            )

        if not normalized:
            normalized = [dict(item) for item in DEFAULT_SCHEDULED_WINDOWS]

        return normalized

    def _normalize_quiet_hours(self, value: object) -> Dict:
        source = value if isinstance(value, dict) else DEFAULT_QUIET_HOURS
        return {
            "enabled": bool(source.get("enabled", DEFAULT_QUIET_HOURS["enabled"])),
            "start": self._normalize_clock_time(source.get("start"), DEFAULT_QUIET_HOURS["start"]),
            "end": self._normalize_clock_time(source.get("end"), DEFAULT_QUIET_HOURS["end"]),
        }

    def _normalize_clock_time(self, value: object, fallback: str) -> str:
        raw = str(value or fallback).strip()
        try:
            parsed = datetime.strptime(raw, "%H:%M")
            return parsed.strftime("%H:%M")
        except ValueError:
            return fallback

    def _coerce_int(self, value: object, fallback: int, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = fallback
        return max(minimum, min(maximum, number))

    def _resolve_target_user(self, channel: Optional[str], external_user_id: Optional[str]) -> Tuple[str, str]:
        target_channel = str(channel or "").strip()
        target_external_user_id = str(external_user_id or "").strip()
        if target_channel and target_external_user_id:
            return target_channel, target_external_user_id

        config = self.get_config()
        target_channel = config["target_channel"]
        target_external_user_id = config["target_external_user_id"]
        if not target_external_user_id:
            raise ValueError("请先配置主动聊天目标用户")
        return target_channel, target_external_user_id

    def _build_fallback_message(
        self,
        target_channel: str,
        target_external_user_id: str,
        trigger_type: str,
        user_memory: Optional[Dict],
    ) -> str:
        _ = (target_channel, target_external_user_id, user_memory)
        if trigger_type == "inactivity":
            return "刚刚突然想到你了，今天过得怎么样呀？"
        return "刚刚想起你，想来和你说句话，在忙吗？"

    def _resolve_due_trigger(self, config: Dict) -> Optional[Dict]:
        config = self._normalize_config(config)
        if not config.get("enabled") or not config.get("target_external_user_id"):
            return None

        now = datetime.now()
        if self._is_in_quiet_hours(now, config.get("quiet_hours") or {}):
            return None

        db = SessionLocal()
        try:
            user = (
                db.query(User)
                .filter(
                    User.channel == config["target_channel"],
                    User.external_user_id == config["target_external_user_id"],
                )
                .first()
            )
            if not user:
                return None

            last_interaction = user.last_interaction or user.first_interaction or user.created_at
            if last_interaction:
                minutes_since_last_interaction = (now - last_interaction).total_seconds() / 60
                if minutes_since_last_interaction < config["min_interval_minutes"]:
                    return None

            if self._count_sent_today(db, config["target_channel"], config["target_external_user_id"], now) >= config["max_messages_per_day"]:
                return None

            last_sent = self._get_last_success_log(db, config["target_channel"], config["target_external_user_id"])
            if last_sent and (now - last_sent.sent_at).total_seconds() / 60 < config["min_interval_minutes"]:
                return None

            for window in config.get("scheduled_windows") or []:
                if not window.get("enabled"):
                    continue
                if self._is_window_due(now, window["time"]) and not self._window_sent_today(
                    db,
                    config["target_channel"],
                    config["target_external_user_id"],
                    window["key"],
                    now,
                ):
                    return {"trigger_type": "scheduled", "window_key": window["key"]}

            if (
                last_interaction
                and now - last_interaction >= timedelta(hours=config["inactivity_trigger_hours"])
                and not self._already_sent_inactivity_since(
                    db,
                    config["target_channel"],
                    config["target_external_user_id"],
                    last_interaction,
                )
            ):
                return {"trigger_type": "inactivity", "window_key": None}
        finally:
            db.close()

        return None

    def _is_window_due(self, now: datetime, clock_time: str) -> bool:
        scheduled = datetime.strptime(clock_time, "%H:%M").time()
        scheduled_at = now.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)
        delta_seconds = (now - scheduled_at).total_seconds()
        return 0 <= delta_seconds < (self.scheduler_interval_seconds + 5)

    def _is_in_quiet_hours(self, now: datetime, quiet_hours: Dict) -> bool:
        if not quiet_hours.get("enabled"):
            return False

        start = datetime.strptime(quiet_hours["start"], "%H:%M").time()
        end = datetime.strptime(quiet_hours["end"], "%H:%M").time()
        current = now.time()

        if start < end:
            return start <= current < end
        return current >= start or current < end

    def _count_sent_today(self, db, target_channel: str, target_external_user_id: str, now: datetime) -> int:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        return (
            db.query(ProactiveChatLog)
            .filter(
                ProactiveChatLog.target_channel == target_channel,
                ProactiveChatLog.target_external_user_id == target_external_user_id,
                ProactiveChatLog.status == "sent",
                ProactiveChatLog.sent_at >= start_of_day,
                ProactiveChatLog.sent_at < end_of_day,
            )
            .count()
        )

    def _window_sent_today(self, db, target_channel: str, target_external_user_id: str, window_key: str, now: datetime) -> bool:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        return (
            db.query(ProactiveChatLog)
            .filter(
                ProactiveChatLog.target_channel == target_channel,
                ProactiveChatLog.target_external_user_id == target_external_user_id,
                ProactiveChatLog.status == "sent",
                ProactiveChatLog.trigger_type == "scheduled",
                ProactiveChatLog.window_key == window_key,
                ProactiveChatLog.sent_at >= start_of_day,
                ProactiveChatLog.sent_at < end_of_day,
            )
            .first()
            is not None
        )

    def _already_sent_inactivity_since(self, db, target_channel: str, target_external_user_id: str, since: datetime) -> bool:
        return (
            db.query(ProactiveChatLog)
            .filter(
                ProactiveChatLog.target_channel == target_channel,
                ProactiveChatLog.target_external_user_id == target_external_user_id,
                ProactiveChatLog.status == "sent",
                ProactiveChatLog.trigger_type == "inactivity",
                ProactiveChatLog.sent_at >= since,
            )
            .first()
            is not None
        )

    def _get_last_success_log(self, db, target_channel: str, target_external_user_id: str) -> Optional[ProactiveChatLog]:
        return (
            db.query(ProactiveChatLog)
            .filter(
                ProactiveChatLog.target_channel == target_channel,
                ProactiveChatLog.target_external_user_id == target_external_user_id,
                ProactiveChatLog.status == "sent",
            )
            .order_by(ProactiveChatLog.sent_at.desc(), ProactiveChatLog.id.desc())
            .first()
        )


proactive_chat_service = ProactiveChatService()
