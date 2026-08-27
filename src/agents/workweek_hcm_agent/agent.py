"""WorkWeek HCM Agent implementation."""
from typing import Any, Dict
from .prompts import WORKWEEK_HCM_AGENT_SYSTEM_PROMPT
from .tools import get_employee_profile, get_leave_balance, submit_time_off_request


class WorkWeekHCMAgent:
    """Sub-agent responsible for WorkWeek HCM operations (PTO, profiles, time-off)."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.name = "WorkWeek HCM Agent"
        self.model_name = model_name
        self.system_prompt = WORKWEEK_HCM_AGENT_SYSTEM_PROMPT
        self.tools = [get_employee_profile, get_leave_balance, submit_time_off_request]

    async def execute_task(self, task: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute HCM task."""
        raise NotImplementedError("WorkWeek HCM agent execution to be implemented.")
