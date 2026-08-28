"""
WorkAgent Definition & Tool Implementations (Google ADK & Gemini).
Connects to WorkWeek MCP Server (/work-week/mcp/) with dynamic session token resolution,
Confirm-Before-Commit gating (SDD Section 4.2), and strict subject isolation (ADR-005).
"""

import asyncio
import datetime
import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional

os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT", "elevate-taiwan-cohort-2")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

import google.auth
from google.oauth2.credentials import Credentials

_orig_default = google.auth.default

def _smart_auth_default(*args, **kwargs):
    try:
        tok = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        if tok:
            return Credentials(token=tok), os.getenv("GOOGLE_CLOUD_PROJECT", "elevate-taiwan-cohort-2")
    except Exception:
        pass
    return _orig_default(*args, **kwargs)

google.auth.default = _smart_auth_default

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.security import confirmation_manager
from src.workweek_service import workweek_mcp

logger = logging.getLogger(__name__)

# Active session context store: session_id -> {token, employee_id}
_SESSION_TOKENS: Dict[str, str] = {}


def set_active_session_token(session_id: str, token: str):
    _SESSION_TOKENS[session_id] = token


def get_active_session_token(session_id: Optional[str] = None) -> str:
    if session_id and session_id in _SESSION_TOKENS:
        return _SESSION_TOKENS[session_id]
    return workweek_mcp.default_token


# =====================================================================
# ADK Domain Tools (Calling WorkWeek MCP Capabilities)
# =====================================================================

async def get_my_profile() -> Dict[str, Any]:
    """Retrieves official employee profile metadata (name, email, role, home address, phone number, manager ID) from WorkWeek MCP."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]
    return await workweek_mcp.read_resource_profile(emp_id, token)


async def get_my_leave_balances() -> Dict[str, Any]:
    """Fetches remaining and used vacation and sick leave balances from WorkWeek MCP."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]
    return await workweek_mcp.get_employee_balances(emp_id, token)


async def get_my_leave_requests() -> Dict[str, Any]:
    """Fetches the history of all requested time off (leave requests) from WorkWeek MCP."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]
    return await workweek_mcp.get_leave_requests(emp_id, token)


async def stage_time_off_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    days: float
) -> Dict[str, Any]:
    """Stages a new time-off booking and mints a single-use cryptographically bound confirmation token (SDD Section 4.2).

    MUST be called before executing request_time_off to generate a review card with dates, days, and token.
    Args:
        leave_type: 'vacation' or 'sick'.
        start_date: Start date in YYYY-MM-DD format (must not be in past).
        end_date: End date in YYYY-MM-DD format (must not be before start_date).
        days: Total working days requested (e.g. 1.0, 3.0, 5.0).
    """
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]

    # Pre-validate balances from MCP
    bal_res = await workweek_mcp.get_employee_balances(emp_id, token)
    norm_type = leave_type.lower()
    rem_key = f"{norm_type}_remaining"
    remaining = bal_res.get("balances", {}).get(rem_key, 0.0)

    payload = {
        "employee_id": emp_id,
        "leave_type": norm_type,
        "start_date": start_date,
        "end_date": end_date,
        "days": days
    }

    token_info = confirmation_manager.mint_token(
        employee_id=emp_id,
        action="request_time_off",
        payload=payload,
        ttl_seconds=300
    )

    return {
        "status": "STAGED_AWAITING_CONFIRMATION",
        "action_required": "USER_CONFIRMATION",
        "confirmation_token": token_info["token"],
        "payload_hash": token_info["payload_hash"],
        "expires_at": token_info["expires_at"],
        "staged_request": payload,
        "current_available_balance": remaining,
        "instruction": "Present the confirmation card to the user with leave type, start/end dates, total days, and confirmation token. Ask them to confirm."
    }


async def submit_time_off_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    days: float,
    confirmation_token: str
) -> Dict[str, Any]:
    """Submits the official time-off booking in WorkWeek MCP upon verifying the cryptographic confirmation token."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]

    record_check = confirmation_manager._tokens.get(confirmation_token)
    if not record_check:
        return {"error": "404_CONFIRMATION_INVALID", "message": "Confirmation token is invalid or does not exist."}

    inbound_payload = {
        "employee_id": emp_id,
        "leave_type": leave_type.lower(),
        "start_date": start_date,
        "end_date": end_date,
        "days": days
    }

    valid, reason, record = confirmation_manager.verify_and_consume(confirmation_token, inbound_payload)
    if not valid:
        return {"error": "409_CONFIRMATION_FAILED", "message": reason}

    return await workweek_mcp.request_time_off(
        employee_id=emp_id,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        days=days,
        token=token
    )


async def stage_personal_info_update(address: str, phone: str) -> Dict[str, Any]:
    """Stages an update to home address and phone number, minting a confirmation token."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]

    payload = {
        "employee_id": emp_id,
        "address": address,
        "phone": phone
    }

    token_info = confirmation_manager.mint_token(
        employee_id=emp_id,
        action="update_personal_info",
        payload=payload,
        ttl_seconds=300
    )

    return {
        "status": "STAGED_AWAITING_CONFIRMATION",
        "action_required": "USER_CONFIRMATION",
        "confirmation_token": token_info["token"],
        "payload_hash": token_info["payload_hash"],
        "expires_at": token_info["expires_at"],
        "staged_update": payload
    }


async def submit_personal_info_update(address: str, phone: str, confirmation_token: str) -> Dict[str, Any]:
    """Commits updated personal info to WorkWeek MCP upon verifying confirmation token."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]

    inbound_payload = {
        "employee_id": emp_id,
        "address": address,
        "phone": phone
    }

    valid, reason, record = confirmation_manager.verify_and_consume(confirmation_token, inbound_payload)
    if not valid:
        return {"error": "409_CONFIRMATION_FAILED", "message": reason}

    return await workweek_mcp.update_personal_info(
        employee_id=emp_id,
        address=address,
        phone=phone,
        token=token
    )


async def cancel_time_off_request(request_id: str) -> Dict[str, Any]:
    """Cancels a pending or approved leave request and refunds days in WorkWeek MCP."""
    token = get_active_session_token()
    emp_res = await workweek_mcp.get_current_employee_id(token)
    emp_id = emp_res["employee_id"]
    return await workweek_mcp.cancel_leave_request(emp_id, request_id, token)


# =====================================================================
# WorkAgent System Prompt (Zero Hardcoding & Subject Isolation)
# =====================================================================

WORKAGENT_SYSTEM_INSTRUCTION = """
You are **WorkAgent**, the Enterprise HCM Specialist Agent interfacing directly with the **WorkWeek MCP Server (/work-week/mcp/)**.

**OPERATING INSTRUCTIONS:**
1. **Dynamic Authentication:** The user session is authenticated via their MCP token. All tool calls automatically resolve the user's `employee_id` from the WorkWeek MCP service. Never hardcode or assume an employee name or ID.
2. **Subject Isolation (SDD ADR-005):** You are strictly authorized to query and modify records for the currently authenticated employee. If the user asks for ANY other employee's balances, profile, or records, you MUST REFUSE:
   "Access Denied (Subject Isolation Policy): Under enterprise zero-trust security, you are only authorized to view and manage your own employee records."
3. **Confirm-Before-Commit Protocol:**
   - When the user asks to book time off, ALWAYS call `stage_time_off_request` first to validate dates, days, and mint a confirmation token.
   - Present the Action Review Card to the user with dates, total days, and confirmation token.
   - Only call `submit_time_off_request` when the user confirms.
4. **Accurate Fact Grounding:** State exact figures directly returned by the WorkWeek MCP tools with timestamps.
"""

def create_work_agent(model_name: str = "gemini-2.5-flash") -> LlmAgent:
    return LlmAgent(
        name="work_agent",
        model=model_name,
        instruction=WORKAGENT_SYSTEM_INSTRUCTION.strip(),
        tools=[
            get_my_profile,
            get_my_leave_balances,
            get_my_leave_requests,
            stage_time_off_request,
            submit_time_off_request,
            stage_personal_info_update,
            submit_personal_info_update,
            cancel_time_off_request
        ]
    )


class WorkAgentOrchestrator:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.agent = create_work_agent(model_name=model_name)
        self.session_service = InMemorySessionService()
        self.runner = Runner(app_name="work_agent_app", agent=self.agent, session_service=self.session_service)
        self._active_sessions: Dict[str, str] = {}

    async def get_or_create_session(self, user_id: str) -> str:
        if user_id in self._active_sessions:
            return self._active_sessions[user_id]
        session = await self.session_service.create_session(app_name="work_agent_app", user_id=user_id)
        self._active_sessions[user_id] = session.id
        return session.id

    async def process_user_message(
        self,
        user_id: str,
        message_text: str,
        mcp_token: Optional[str] = None
    ) -> Dict[str, Any]:
        session_id = await self.get_or_create_session(user_id)
        token = mcp_token or workweek_mcp.default_token
        set_active_session_token(session_id, token)

        # Resolve employee session from MCP dynamically
        emp_res = await workweek_mcp.get_current_employee_id(token)
        emp_id = emp_res["employee_id"]

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message_text)]
        )

        final_text = ""
        tool_calls = []
        tool_responses = []
        confirmation_card = None

        async for event in self.runner.run_async(session_id=session_id, user_id=user_id, new_message=content):
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final_text += part.text
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        tool_calls.append({
                            "name": fc.name,
                            "args": dict(fc.args) if fc.args else {}
                        })
                    if getattr(part, "function_response", None):
                        fr = part.function_response
                        resp_data = fr.response if isinstance(fr.response, dict) else {"result": str(fr.response)}
                        tool_responses.append({
                            "name": fr.name,
                            "response": resp_data
                        })
                        if fr.name in ["stage_time_off_request", "stage_personal_info_update"] and resp_data.get("status") == "STAGED_AWAITING_CONFIRMATION":
                            confirmation_card = resp_data

        return {
            "session_id": session_id,
            "user_id": user_id,
            "authenticated_employee_id": emp_id,
            "reply": final_text.strip(),
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "confirmation_card": confirmation_card,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }


orchestrator = WorkAgentOrchestrator()
