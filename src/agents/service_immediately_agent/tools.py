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
    "mcp_AXf29vsAz5TxRQmKP8CHXYZrwP_MAr_iDtnC6kDm13I",
)


def format_tickets_output(tickets_json_str: str) -> str:
    """Parse and format ticket JSON records into a human-readable string."""
    try:
        tickets = json.loads(tickets_json_str)
        if not isinstance(tickets, list):
            return tickets_json_str

        output = [f"Found {len(tickets)} ticket record(s):\n"]
        for idx, ticket in enumerate(tickets, start=1):
            output.append(f"--- Ticket #{idx} ---")
            output.append(f"  • Ticket ID: {ticket.get('ticket_id')}")
            output.append(f"  • Requested By: {ticket.get('caller_name')} ({ticket.get('requested_by')})")
            output.append(f"  • Category: {ticket.get('category')}")
            output.append(f"  • Priority: {ticket.get('priority')}")
            output.append(f"  • Status: {ticket.get('status')}")
            output.append(f"  • Assignment Group: {ticket.get('assignment_group')}")
            output.append(f"  • Assignee: {ticket.get('assigned_to')}")
            output.append(f"  • Short Description: {ticket.get('short_description')}")
            output.append(f"  • Created At: {ticket.get('created_at')}\n")
        return "\n".join(output)
    except Exception:
        return tickets_json_str


async def call_service_immediately_mcp(
    tool_name: str,
    arguments: Dict[str, Any],
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_token: str = DEFAULT_MCP_TOKEN,
    timeout: float = 20.0,
) -> str:
    """Directly invoke a tool on the ServiceImmediately MCP server."""
    headers = {
        "X-MCP-Token": mcp_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.call_tool(name=tool_name, arguments=arguments)
                result_text = "\n".join([c.text for c in tool_result.content if hasattr(c, "text")])
                return result_text
