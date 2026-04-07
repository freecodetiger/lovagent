"""
Web search tool boundary.
"""

from __future__ import annotations

from typing import Dict

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.services.llm_service import glm_service


class WebSearchToolInput(BaseModel):
    user_message: str = Field(..., description="Current user message")


@tool("web_search_tool", args_schema=WebSearchToolInput)
async def web_search_tool(user_message: str) -> Dict[str, object]:
    """Collect optional web context for the current user message."""
    return await glm_service.maybe_collect_web_context(user_message)
