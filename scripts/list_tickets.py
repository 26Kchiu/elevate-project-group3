"""CLI utility to query and list tickets from ServiceImmediately MCP Server."""

import asyncio
import json
import sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from src.agents.service_immediately_agent.tools import DEFAULT_MCP_TOKEN, DEFAULT_MCP_URL, format_tickets_output

EMPLOYEE_ID = sys.argv[1] if len(sys.argv) > 1 else "EMP-561"


async def main():
    print("=" * 60)
    print(f"[*] Querying tickets for Employee ID: {EMPLOYEE_ID}")
    print(f"[*] Connecting to ITSM (ServiceImmediately): {DEFAULT_MCP_URL}")
    print("=" * 60 + "\n")

    headers = {"X-MCP-Token": DEFAULT_MCP_TOKEN}
    async with httpx.AsyncClient(headers=headers, timeout=15.0) as http_client:
        async with streamable_http_client(DEFAULT_MCP_URL, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[✓] MCP Session initialized successfully.")
                print(f"[*] Querying tickets for {EMPLOYEE_ID}...")

                result = await session.call_tool("list_tickets", arguments={"employee_id": EMPLOYEE_ID})
                raw_text = "\n".join([c.text for c in result.content if hasattr(c, "text")])
                print(format_tickets_output(raw_text))


if __name__ == "__main__":
    asyncio.run(main())
