"""WorkWeek HCM Agent implementation."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from google import genai
from google.genai import types
from google.oauth2 import credentials
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Disable mTLS environment configurations to prevent corporate proxy/cert errors
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"

from .prompts import DEFAULT_EMPLOYEE_ID, get_system_instruction
from .tools import DEFAULT_MCP_TOKEN, DEFAULT_MCP_URL

DEFAULT_MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.7-flash")


class WorkWeekHCMAgent:
    """Sub-agent responsible for WorkWeek HCM operations (balances, profile, time-off requests)."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        mcp_url: str = DEFAULT_MCP_URL,
        mcp_token: str = DEFAULT_MCP_TOKEN,
        employee_id: str = DEFAULT_EMPLOYEE_ID,
    ):
        self.name = "WorkWeek HCM Agent"
        self.model_name = model_name
        self.mcp_url = mcp_url
        self.mcp_token = mcp_token
        self.employee_id = employee_id

        self.genai_client = self._init_genai_client()

    def _init_genai_client(self) -> genai.Client:
        """Initialize Google GenAI client supporting API Key, Vertex AI, or gcloud OAuth token."""
        if "GEMINI_API_KEY" in os.environ:
            return genai.Client()

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "harry-project-elevate")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

        try:
            token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
            creds = credentials.Credentials(token)
            return genai.Client(vertexai=True, project=project_id, location=location, credentials=creds)
        except Exception:
            return genai.Client(vertexai=True, project=project_id, location=location)

    async def run(
        self,
        user_prompt: str,
        employee_id: Optional[str] = None,
        mcp_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the WorkWeek HCM agent with dynamic MCP tool discovery and execution loop."""
        active_emp_id = employee_id or self.employee_id
        active_token = mcp_token or self.mcp_token
        system_instruction = get_system_instruction(active_emp_id)

        headers = {
            "X-MCP-Token": active_token,
            "Content-Type": "application/json",
        }

        print(f"\n{'=' * 55}")
        print(f"[*] Starting {self.name} (Model: {self.model_name})")
        print(f"[*] MCP Endpoint: {self.mcp_url}")
        print(f"[*] Employee ID: {active_emp_id}")
        print(f"[*] User Prompt: {user_prompt}")
        print(f"{'=' * 55}\n")

        tool_calls_record: List[Dict[str, Any]] = []
        tool_responses_record: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(headers=headers, timeout=25.0) as http_client:
            async with streamable_http_client(self.mcp_url, http_client=http_client) as streams:
                read_stream, write_stream = streams[0], streams[1]
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
                            tool_args = dict(call.args) if call.args else {}
                            print(f"[Agent -> Tool Call] Invoking WorkWeek MCP `{tool_name}`: {json.dumps(tool_args, ensure_ascii=False)}")
                            tool_calls_record.append({"name": tool_name, "args": tool_args})

                            # Execute remote tool on WorkWeek MCP Server
                            tool_result = await session.call_tool(name=tool_name, arguments=tool_args)
                            result_text = "\n".join([c.text for c in tool_result.content if hasattr(c, "text")])
                            print(f"[MCP -> Agent Result] Response payload: {result_text}\n")
                            tool_responses_record.append({"name": tool_name, "response": result_text})

                            # Send tool execution result back to Gemini
                            response = chat.send_message(
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": result_text},
                                )
                            )

                    reply_text = response.text or ""
                    print("-" * 55)
                    print(f"[Agent Response]:\n{reply_text}")
                    print("-" * 55 + "\n")

                    return {
                        "agent_name": self.name,
                        "model": self.model_name,
                        "reply": reply_text,
                        "employee_id": active_emp_id,
                        "tool_calls": tool_calls_record,
                        "tool_responses": tool_responses_record,
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }

    async def execute_task(self, task: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Unified interface for Root Orchestrator."""
        parameters = parameters or {}
        emp_id = parameters.get("employee_id", self.employee_id)
        mcp_tok = parameters.get("mcp_token", self.mcp_token)

        result_payload = await self.run(user_prompt=task, employee_id=emp_id, mcp_token=mcp_tok)
        return {
            "agent_name": self.name,
            "model": self.model_name,
            "result": result_payload["reply"],
            "tool_calls": result_payload["tool_calls"],
            "tool_responses": result_payload["tool_responses"],
            "status": "success",
        }


async def main():
    agent = WorkWeekHCMAgent()
    # Test Scenario: Query employee's leave balances in English
    result = await agent.run("What are my current remaining vacation and sick leave balances?")
    print(f"\nFinal Result from {agent.model_name}:\n{result['reply']}")


if __name__ == "__main__":
    asyncio.run(main())
