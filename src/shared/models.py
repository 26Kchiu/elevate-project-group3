"""Data models for HR system requests, policy queries, context, and responses."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    user_id: str
    query: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClauseCitation(BaseModel):
    clause_ref: str
    title: str
    verbatim_text: str
    doc_id: str = "POL-SG-HANDBOOK-001"
    version: int = 2
    page_number: Optional[int] = None
    section_ref: Optional[str] = None


class PolicyQueryResponse(BaseModel):
    response_class: str  # "direct", "composed", "refuse"
    text: str
    citations: List[str] = Field(default_factory=list)
    governing_clauses: List[Dict[str, Any]] = Field(default_factory=list)
    unmet_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    response: str
    agent_name: str
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list)
    policy_data: Optional[PolicyQueryResponse] = None
