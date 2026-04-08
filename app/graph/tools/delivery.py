"""
Message delivery tool boundary.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.graph.executors.delivery import deliver_incoming_reply, deliver_proactive_outreach


class MessageDeliveryToolInput(BaseModel):
    delivery_kind: Literal["incoming_reply", "proactive_outreach"] = Field(..., description="Delivery scenario")
    channel: str = Field(..., description="Target channel")
    external_user_id: str = Field(..., description="Target external user id")
    content: str = Field(..., description="Message content")
    trigger_type: Optional[str] = Field(default=None, description="Proactive trigger type")
    window_key: Optional[str] = Field(default=None, description="Scheduled window key")


@tool("message_delivery_tool", args_schema=MessageDeliveryToolInput)
async def message_delivery_tool(
    delivery_kind: Literal["incoming_reply", "proactive_outreach"],
    channel: str,
    external_user_id: str,
    content: str,
    trigger_type: Optional[str] = None,
    window_key: Optional[str] = None,
) -> Dict[str, object]:
    """Deliver a message through the configured executor boundary."""
    if delivery_kind == "incoming_reply":
        return await deliver_incoming_reply(channel=channel, external_user_id=external_user_id, content=content)

    return await deliver_proactive_outreach(
        target_channel=channel,
        target_external_user_id=external_user_id,
        trigger_type=trigger_type or "",
        window_key=window_key,
        content=content,
    )
