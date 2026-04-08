"""
Channel-aware outbound dispatcher.
"""

from __future__ import annotations

from typing import Dict

from app.services.wecom_service import wecom_service


class ChannelDispatcher:
    async def send_text(self, channel: str, external_user_id: str, content: str) -> Dict[str, object]:
        lowered = (channel or "").strip().lower()
        if lowered == "wecom":
            await wecom_service.send_text_message(external_user_id, content)
            return {"channel": "wecom", "status": "sent"}

        if lowered == "napcat":
            from app.services.napcat_service import napcat_service

            await napcat_service.send_private_text(external_user_id, content)
            return {"channel": "napcat", "status": "sent"}

        raise ValueError(f"Unsupported channel: {channel}")


channel_dispatcher = ChannelDispatcher()

