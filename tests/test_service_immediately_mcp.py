"""Test connectivity and tool discovery for ServiceImmediately MCP Server."""

import asyncio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from src.agents.service_immediately_agent.tools import DEFAULT_MCP_TOKEN, DEFAULT_MCP_URL


async def test_connectivity():
    print(f"[*] Connecting to ServiceImmediately MCP Endpoint: {DEFAULT_MCP_URL}")
    headers = {"X-MCP-Token": DEFAULT_MCP_TOKEN}

    async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
        async with streamable_http_client(DEFAULT_MCP_URL, http_client=client) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[✓] MCP Session initialized successfully!\n")

                # List tools
                tools_response = await session.list_tools()
                print(f"[✓] Retrieved {len(tools_response.tools)} Tools:")
                for tool in tools_response.tools:
                    print(f"  - Name: {tool.name}")
                    print(f"    Description: {tool.description}")
                    input_schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", {}))
                    properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else getattr(input_schema, "properties", {})
                    print(f"    Parameters: {list(properties.keys()) if isinstance(properties, dict) else properties}\n")


if __name__ == "__main__":
    asyncio.run(test_connectivity())
