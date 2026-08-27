"""WorkWeek HCM Agent Package."""

from .agent import WorkWeekHCMAgent
from .prompts import WORKWEEK_HCM_AGENT_SYSTEM_PROMPT, get_system_instruction
from .tools import (
    DEFAULT_MCP_TOKEN,
    DEFAULT_MCP_URL,
    call_workweek_mcp,
    cancel_leave_request,
    get_current_employee_id,
    get_employee_balances,
    get_leave_requests,
    get_personal_info,
    request_time_off,
    update_personal_info,
)

__all__ = [
    "WorkWeekHCMAgent",
    "WORKWEEK_HCM_AGENT_SYSTEM_PROMPT",
    "get_system_instruction",
    "DEFAULT_MCP_URL",
    "DEFAULT_MCP_TOKEN",
    "call_workweek_mcp",
    "get_current_employee_id",
    "get_employee_balances",
    "get_personal_info",
    "get_leave_requests",
    "request_time_off",
    "update_personal_info",
    "cancel_leave_request",
]
