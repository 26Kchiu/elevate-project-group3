"""ServiceImmediately Agent implementation."""
from typing import Any, Dict
from .prompts import SERVICE_IMMEDIATELY_AGENT_SYSTEM_PROMPT
from .tools import create_ticket, get_ticket_status, update_ticket


class ServiceImmediatelyAgent:
    """Sub-agent responsible for ServiceImmediately ticketing and service desk workflows."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.name = "ServiceImmediately Agent"
        self.model_name = model_name
        self.system_prompt = SERVICE_IMMEDIATELY_AGENT_SYSTEM_PROMPT
        self.tools = [create_ticket, get_ticket_status, update_ticket]

    async def execute_task(self, task: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute ticketing task."""
        raise NotImplementedError("ServiceImmediately agent execution to be implemented.")
