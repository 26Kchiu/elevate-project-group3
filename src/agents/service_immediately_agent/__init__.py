"""ServiceImmediately Agent package."""

from .agent import ServiceImmediatelyAgent
from .prompts import DEFAULT_EMPLOYEE_ID, SERVICE_IMMEDIATELY_SYSTEM_PROMPT, get_system_instruction
from .tools import DEFAULT_MCP_TOKEN, DEFAULT_MCP_URL, call_service_immediately_mcp, format_tickets_output

__all__ = [
    "ServiceImmediatelyAgent",
    "DEFAULT_EMPLOYEE_ID",
    "SERVICE_IMMEDIATELY_SYSTEM_PROMPT",
    "get_system_instruction",
    "DEFAULT_MCP_URL",
    "DEFAULT_MCP_TOKEN",
    "call_service_immediately_mcp",
    "format_tickets_output",
]
