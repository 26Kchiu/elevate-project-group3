"""Data models for HR system requests, context, and responses."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    user_id: str
    query: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    response: str
    agent_name: str
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list)
