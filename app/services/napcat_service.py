"""
NapCat OneBot11 forward WebSocket client service.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Optional

from app.config import settings
from app.services.runtime_config_service import runtime_config_service

try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

class NapCatService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._ws = None
        self._send_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

    def _config(self) -> dict:
        runtime = runtime_config_service.get_effective_napcat_config()
        return {
            "ws_url": runtime.get("ws_url") or settings.napcat_ws_url,
            "ws_token": runtime.get("ws_token") or settings.napcat_ws_token,
        }

    async def start(self) -> None:
        if websockets is None:
            logger.warning("NapCat disabled: websockets is unavailable")
            return
        if self._task and not self._task.done():
            return
        cfg = self._config()
        if not str(cfg["ws_url"]).strip():
            logger.warning("NapCat disabled: NAPCAT_WS_URL is empty")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _run_loop(self) -> None:
        delay = 1.0
        while not self._stop_event.is_set():
            cfg = self._config()
            ws_url = str(cfg["ws_url"]).strip()
            if not ws_url:
                return
            headers = {}
            token = str(cfg.get("ws_token") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                async with websockets.connect(ws_url, additional_headers=headers) as ws:
                    self._ws = ws
                    delay = 1.0
                    async for message in ws:
                        await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("NapCat connection error: %s", exc)
            finally:
                self._ws = None

            sleep_seconds = min(30.0, delay + random.uniform(0, 0.8))
            await asyncio.sleep(sleep_seconds)
            delay = min(30.0, delay * 2)

    async def _handle_message(self, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return

        if payload.get("post_type") != "message":
            return
        if payload.get("message_type") != "private":
            return

        content = str(payload.get("raw_message") or "").strip()
        external_user_id = str(payload.get("user_id") or "").strip()
        if not content or not external_user_id:
            return

        from app.graph import run_incoming_message_graph

        await run_incoming_message_graph(
            {
                "channel": "napcat",
                "external_user_id": external_user_id,
                "user_content": content,
            }
        )

    async def send_private_text(self, external_user_id: str, content: str) -> None:
        if not self._ws:
            raise RuntimeError("NapCat websocket is not connected")
        payload = {
            "action": "send_private_msg",
            "params": {"user_id": int(external_user_id) if external_user_id.isdigit() else external_user_id, "message": content},
            "echo": f"lovagent-{int(asyncio.get_running_loop().time() * 1000)}",
        }
        async with self._send_lock:
            await self._ws.send(json.dumps(payload, ensure_ascii=False))


napcat_service = NapCatService()

