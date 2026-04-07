"""
Memory extraction tool boundary.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.services.llm_service import glm_service


class MemoryExtractionToolInput(BaseModel):
    user_message: str = Field(..., description="Latest user message")
    agent_message: str = Field(..., description="Latest agent message")
    existing_memory: Optional[Dict] = Field(default=None, description="Current long-term memory snapshot")
    short_term_memory: Optional[Dict] = Field(default=None, description="Current short-term memory snapshot")
    recent_messages: Optional[List[Dict[str, str]]] = Field(default=None, description="Recent dialogue turns")


@tool("memory_extract_tool", args_schema=MemoryExtractionToolInput)
async def memory_extract_tool(
    user_message: str,
    agent_message: str,
    existing_memory: Optional[Dict] = None,
    short_term_memory: Optional[Dict] = None,
    recent_messages: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, object]:
    """Extract structured memory facts from the latest conversation turn."""
    return await glm_service.extract_memory_facts(
        user_message=user_message,
        agent_message=agent_message,
        existing_memory=existing_memory,
        short_term_memory=short_term_memory,
        recent_messages=recent_messages,
    )
