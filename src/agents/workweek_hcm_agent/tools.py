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


async def call_workweek_mcp(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    timeout: float = 20.0,
) -> str:
    """Directly invoke a tool on the WorkWeek MCP server."""
    arguments = arguments or {}
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
) -> str:
    """Retrieve leave balances (vacation & sick) for an employee."""
    return await call_workweek_mcp("get_employee_balances", {"employee_id": employee_id}, mcp_url, mcp_token)


async def get_personal_info(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Retrieve contact information (address & phone) for an employee."""
    return await call_workweek_mcp("get_personal_info", {"employee_id": employee_id}, mcp_url, mcp_token)


async def get_leave_requests(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Retrieve history of all submitted leave requests for an employee."""
    return await call_workweek_mcp("get_leave_requests", {"employee_id": employee_id}, mcp_url, mcp_token)


async def request_time_off(
    employee_id: str,
    start_date: str,
    end_date: str,
    leave_type: str,
    days: float,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Submit a time off request in WorkWeek."""
    args = {
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "leave_type": leave_type,
        "days": days,
    }
    return await call_workweek_mcp("request_time_off", args, mcp_url, mcp_token)


async def update_personal_info(
    employee_id: str,
    address: str,
    phone: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Update personal contact information for an employee in WorkWeek."""
    args = {
        "employee_id": employee_id,
        "address": address,
        "phone": phone,
    }
    return await call_workweek_mcp("update_personal_info", args, mcp_url, mcp_token)


async def cancel_leave_request(
    employee_id: str,
    request_id: int,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Cancel an active/pending leave request in WorkWeek and refund days."""
    args = {
        "employee_id": employee_id,
        "request_id": int(request_id),
    }
    return await call_workweek_mcp("cancel_leave_request", args, mcp_url, mcp_token)
