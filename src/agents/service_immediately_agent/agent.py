"""ServiceImmediately Agent implementation."""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import httpx
from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .prompts import DEFAULT_EMPLOYEE_ID, get_system_instruction
from .tools import DEFAULT_MCP_TOKEN, DEFAULT_MCP_URL


class ServiceImmediatelyAgent:
    """Sub-agent specialized in IT Service Management (ITSM) and ServiceImmediately ticketing."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        mcp_url: str = DEFAULT_MCP_URL,
        mcp_token: str = DEFAULT_MCP_TOKEN,
        employee_id: str = DEFAULT_EMPLOYEE_ID,
    ):
        self.name = "ServiceImmediately Agent"
        self.model_name = model_name
        self.mcp_url = mcp_url
        self.mcp_token = mcp_token
        self.employee_id = employee_id

        # Auto-detect Gemini API Key vs GCP Vertex AI
        if "GEMINI_API_KEY" in os.environ:
            self.genai_client = genai.Client()
        else:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "host-project-350411")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            self.genai_client = genai.Client(vertexai=True, project=project_id, location=location)

    async def run(self, user_prompt: str, employee_id: Optional[str] = None) -> str:
        """Run the ServiceImmediately agent with dynamic MCP tool discovery and execution loop."""
        active_emp_id = employee_id or self.employee_id
        system_instruction = get_system_instruction(active_emp_id)

        headers = {
            "X-MCP-Token": self.mcp_token,
            "Content-Type": "application/json",
        }

        print(f"\n{'=' * 55}")
        print(f"[*] Starting {self.name} (Model: {self.model_name})")
        print(f"[*] MCP Endpoint: {self.mcp_url}")
        print(f"[*] User Prompt: {user_prompt}")
        print(f"{'=' * 55}\n")

        async with httpx.AsyncClient(headers=headers, timeout=20.0) as http_client:
            async with streamable_http_client(self.mcp_url, http_client=http_client) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    # 1. Initialize MCP session and retrieve tools dynamically
                    await session.initialize()
                    mcp_tools = await session.list_tools()

                    # 2. Convert MCP tool schemas into Gemini Function Declarations
                    func_declarations = []
                    for tool in mcp_tools.tools:
                        input_schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", {}))
                        if not isinstance(input_schema, dict):
                            input_schema = input_schema.model_dump() if hasattr(input_schema, "model_dump") else {}

                        func_declarations.append(
                            types.FunctionDeclaration(
                                name=tool.name,
                                description=tool.description or "",
                                parameters=input_schema,
                            )
                        )

                    gemini_tools = [types.Tool(function_declarations=func_declarations)]

                    # 3. Create Gemini chat session
                    chat = self.genai_client.chats.create(
                        model=self.model_name,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=gemini_tools,
                            temperature=0.1,
                        ),
                    )

                    # 4. Process user request & execute function calling loop
                    response = chat.send_message(user_prompt)

                    while response.function_calls:
                        for call in response.function_calls:
                            tool_name = call.name
                            tool_args = call.args
                            print(f"[Agent -> Tool Call] Invoking MCP Tool `{tool_name}`: {json.dumps(tool_args, ensure_ascii=False)}")

                            # Execute remote tool on MCP Server
                            tool_result = await session.call_tool(name=tool_name, arguments=tool_args)
                            result_text = "\n".join([c.text for c in tool_result.content if hasattr(c, "text")])
                            print(f"[MCP -> Agent Result] Response payload: {result_text}\n")

                            # Send tool execution result back to Gemini
                            response = chat.send_message(
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": result_text},
                                )
                            )

                    print("-" * 55)
                    print(f"[Agent Response]:\n{response.text}")
                    print("-" * 55 + "\n")
                    return response.text

    async def execute_task(self, task: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Unified interface for Root Orchestrator."""
        parameters = parameters or {}
        emp_id = parameters.get("employee_id", self.employee_id)
        result_text = await self.run(user_prompt=task, employee_id=emp_id)
        return {
            "agent_name": self.name,
            "result": result_text,
            "status": "success",
        }


async def main():
    agent = ServiceImmediatelyAgent()
    # Test Scenario: Query employee's open incident tickets
    await agent.run("請幫我查詢我目前名下有哪些已建立的 IT 支援或 incident tickets？")


if __name__ == "__main__":
    asyncio.run(main())
