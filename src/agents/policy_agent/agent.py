"""Policy Agent implementation."""
from typing import Any, Dict
from .prompts import POLICY_AGENT_SYSTEM_PROMPT
from .tools import search_hr_policy


class PolicyAgent:
    """Sub-agent responsible for HR policies and knowledge retrieval."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.name = "Policy Agent"
        self.model_name = model_name
        self.system_prompt = POLICY_AGENT_SYSTEM_PROMPT
        self.tools = [search_hr_policy]

    async def process_query(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process policy inquiry."""
        raise NotImplementedError("Policy agent query processing to be implemented.")
