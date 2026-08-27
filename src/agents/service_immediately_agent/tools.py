"""Tools and helper utilities for ServiceImmediately Agent and MCP interactions."""

import json
import os
from typing import Any, Dict, List, Optional
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_MCP_URL = os.environ.get(
    "SERVICE_IMMEDIATELY_MCP_URL",
    "https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/",
)
DEFAULT_MCP_TOKEN = os.environ.get(
    "SERVICE_IMMEDIATELY_MCP_TOKEN",
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


def format_tickets_output(tickets_json_str: str) -> str:
    """Parse and format ticket JSON records into a human-readable string."""
    try:
        tickets = json.loads(tickets_json_str) if isinstance(tickets_json_str, str) else tickets_json_str
        if not isinstance(tickets, list):
            return str(tickets_json_str)

        if not tickets:
            return "No incident tickets found for this employee."

        output = [f"Found {len(tickets)} incident ticket record(s):\n"]
        for idx, ticket in enumerate(tickets, start=1):
            output.append(f"--- Ticket #{idx} ---")
            output.append(f"  • Ticket ID: {ticket.get('ticket_id')}")
            output.append(f"  • Requested By: {ticket.get('caller_name', '')} ({ticket.get('requested_by')})")
            output.append(f"  • Category: {ticket.get('category')}")
            output.append(f"  • Priority: {ticket.get('priority')}")
            output.append(f"  • Status: {ticket.get('status')}")
            output.append(f"  • Assignment Group: {ticket.get('assignment_group')}")
            output.append(f"  • Assignee: {ticket.get('assigned_to')}")
            output.append(f"  • Short Description: {ticket.get('short_description')}")
            output.append(f"  • Created At: {ticket.get('created_at')}\n")
        return "\n".join(output)
    except Exception:
        return str(tickets_json_str)


async def call_service_immediately_mcp(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
    timeout: float = 20.0,
) -> str:
    """Directly invoke a tool on the ServiceImmediately MCP server with subject isolation validation."""
    arguments = arguments or {}

    # Strict Access Control: Enforce Subject Isolation before outbound invocation
    target_id = arguments.get("employee_id") or arguments.get("requested_by")
    if target_id and authenticated_employee_id:
        violation = enforce_subject_isolation(target_id, authenticated_employee_id)
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


async def list_tickets(
    employee_id: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Retrieve all incident tickets for an employee."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(employee_id, authenticated_employee_id)
        if violation:
            return violation
    return await call_service_immediately_mcp(
        "list_tickets",
        {"employee_id": employee_id},
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def create_ticket(
    requested_by: str,
    category: str,
    short_description: str,
    priority: str = "3 - Moderate",
    assignment_group: str = "Service Desk",
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    authenticated_employee_id: Optional[str] = None,
) -> str:
    """Create a new ServiceImmediately incident ticket."""
    if authenticated_employee_id:
        violation = enforce_subject_isolation(requested_by, authenticated_employee_id)
        if violation:
            return violation
    args = {
        "requested_by": requested_by,
        "category": category,
        "short_description": short_description,
        "priority": priority,
        "assignment_group": assignment_group,
    }
    return await call_service_immediately_mcp(
        "create_ticket",
        args,
        mcp_url,
        mcp_token,
        authenticated_employee_id=authenticated_employee_id,
    )


async def add_ticket_comment(
    ticket_id: str,
    author: str,
    comment: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Append a comment to a ServiceImmediately ticket's activity log."""
    args = {
        "ticket_id": ticket_id,
        "author": author,
        "comment": comment,
    }
    return await call_service_immediately_mcp("add_ticket_comment", args, mcp_url, mcp_token)


async def update_ticket_status(
    ticket_id: str,
    status: str,
    resolution_notes: str = "",
    updated_by: str = "EMP-545",
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
) -> str:
    """Update lifecycle status of a ServiceImmediately ticket."""
    args = {
        "ticket_id": ticket_id,
        "status": status,
        "resolution_notes": resolution_notes,
        "updated_by": updated_by,
    }
    return await call_service_immediately_mcp("update_ticket_status", args, mcp_url, mcp_token)
