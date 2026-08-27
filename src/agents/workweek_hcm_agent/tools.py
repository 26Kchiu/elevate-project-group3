"""Tools and helper utilities for WorkWeek HCM Agent and MCP interactions."""

import json
import os
from typing import Any, Dict, List, Optional
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_MCP_URL = os.environ.get(
    "WORKWEEK_MCP_URL",
    "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/",
)
DEFAULT_MCP_TOKEN = os.environ.get(
    "WORKWEEK_MCP_TOKEN",
    "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg",
)

ACCESS_DENIED_MESSAGE = (
    "Access Denied (Subject Isolation Policy): Under enterprise zero-trust security, "
    "you are only authorized to view and manage your own employee records."
)


def enforce_subject_isolation(target_employee_id: str, authenticated_employee_id: Optional[str]) -> Optional[str]:
    """Validate that target employee ID matches authenticated session employee ID."""
    if not authenticated_employee_id:
        return None
    target_clean = str(target_employee_id).strip().upper()
    auth_clean = str(authenticated_employee_id).strip().upper()
    if target_clean and auth_clean and target_clean != auth_clean:
        return ACCESS_DENIED_MESSAGE
    return None


async def call_workweek_mcp(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
    timeout: float = 20.0,
) -> str:
    """Directly invoke a tool on the WorkWeek MCP server with subject isolation validation."""
    arguments = arguments or {}

    # Strict Access Control: Enforce Subject Isolation before outbound invocation
    if "employee_id" in arguments and authenticated_employee_id:
        violation = enforce_subject_isolation(arguments["employee_id"], authenticated_employee_id)
        if violation:
            return violation

    headers = {
        "X-MCP-Token": mcp_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.call_tool(name=tool_name, arguments=arguments)
                result_text = "\n".join([c.text for c in tool_result.content if hasattr(c, "text")])
                return result_text


async def get_current_employee_id(
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Retrieve the employee ID of the currently authenticated user session."""
    return await call_workweek_mcp("get_current_employee_id", {}, mcp_url, mcp_token)


async def get_employee_balances(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Retrieve leave balances (vacation & sick) for an employee."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    return await call_workweek_mcp(
        "get_employee_balances",
        {"employee_id": employee_id},
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def get_personal_info(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Retrieve contact information (address & phone) for an employee."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    return await call_workweek_mcp(
        "get_personal_info",
        {"employee_id": employee_id},
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def get_leave_requests(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Retrieve history of all submitted leave requests for an employee."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    return await call_workweek_mcp(
        "get_leave_requests",
        {"employee_id": employee_id},
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def request_time_off(
    employee_id: str,
    start_date: str,
    end_date: str,
    leave_type: str,
    days: float,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Submit a time off request in WorkWeek."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    args = {
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "leave_type": leave_type,
        "days": days,
    }
    return await call_workweek_mcp(
        "request_time_off",
        args,
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def update_personal_info(
    employee_id: str,
    address: str,
    phone: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Update personal contact information for an employee in WorkWeek."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    args = {
        "employee_id": employee_id,
        "address": address,
        "phone": phone,
    }
    return await call_workweek_mcp(
        "update_personal_info",
        args,
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def cancel_leave_request(
    employee_id: str,
    request_id: int,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Cancel an active/pending leave request in WorkWeek and refund days."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    args = {
        "employee_id": employee_id,
        "request_id": int(request_id),
    }
    return await call_workweek_mcp(
        "cancel_leave_request",
        args,
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )
