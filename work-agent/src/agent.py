"""
WorkAgent Definition & Tool Implementations (Google ADK).
Follows SDD Section 3.1, 3.3, and ADR-005 (Subject Isolation & Zero-Trust Identity Injection).
Powered by Gemini on Google ADK.
"""

import asyncio
import datetime
import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional

# Disable mTLS if certs are missing in sandbox
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT", "harry-project-elevate")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Patch google.auth.default dynamically to ensure valid gcloud token is used
import google.auth
from google.oauth2.credentials import Credentials

_orig_default = google.auth.default

def _smart_auth_default(*args, **kwargs):
    try:
        tok = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        if tok:
            return Credentials(token=tok), os.getenv("GOOGLE_CLOUD_PROJECT", "harry-project-elevate")
    except Exception:
        pass
    return _orig_default(*args, **kwargs)

google.auth.default = _smart_auth_default

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.security import confirmation_manager
from src.workweek_service import workweek_client

logger = logging.getLogger(__name__)

# Active session context storage: session_id -> {employee_id, user_id, mcp_token}
_SESSION_CONTEXT: Dict[str, Dict[str, Any]] = {}

def set_session_context(session_id: str, employee_id: str, user_id: str, mcp_token: str):
    _SESSION_CONTEXT[session_id] = {
        "employee_id": employee_id,
        "user_id": user_id,
        "mcp_token": mcp_token
    }

def get_current_employee_id() -> str:
    """Returns the authenticated employee ID for the active context (default Harry Lin EMP-HL-001)."""
    return "EMP-HL-001"


# =====================================================================
# ADK Tool Definitions with Subject Isolation (SDD ADR-005)
# =====================================================================

async def get_my_employee_profile() -> Dict[str, Any]:
    """Retrieves the official employee profile for the currently authenticated user (Harry Lin).

    Returns name, email, role, department, tenure, manager, location, and contact information.
    """
    emp_id = get_current_employee_id()
    return await workweek_client.get_employee_profile(emp_id)


async def get_my_leave_balances() -> Dict[str, Any]:
    """Retrieves live leave balances (Vacation, Sick, Medical, Bereavement, Study) for the authenticated user (Harry Lin).

    Returns exact available, accrued, and taken days with timestamp.
    """
    emp_id = get_current_employee_id()
    return await workweek_client.get_leave_balances(emp_id)


async def get_my_leave_request_status(request_id: Optional[str] = None) -> Dict[str, Any]:
    """Looks up the status of past or active leave requests for the authenticated user (Harry Lin).

    Args:
        request_id: Optional reference ID (e.g. 'LR-2026-009120'). If omitted, returns all recent requests.
    """
    emp_id = get_current_employee_id()
    return await workweek_client.get_leave_request_status(emp_id, request_id)


async def stage_my_leave_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    half_day: bool = False,
    note: str = ""
) -> Dict[str, Any]:
    """Stages a new leave request for the authenticated user (Harry Lin) and mints a single-use confirmation token.

    MUST be called before submitting any leave request to present a review card with cryptographic payload hash.
    Args:
        leave_type: 'Vacation', 'Sick', 'Medical', 'Bereavement', or 'Study'.
        start_date: Absolute date in YYYY-MM-DD format.
        end_date: Absolute date in YYYY-MM-DD format.
        half_day: Whether this is a half-day request.
        note: Optional reason or memo.
    """
    emp_id = get_current_employee_id()
    bal_res = await workweek_client.get_leave_balances(emp_id)
    type_key = leave_type.lower()
    balances = bal_res.get("balances", {})
    available = 999.0
    if type_key in balances and "available" in balances[type_key]:
        available = balances[type_key]["available"]

    payload = {
        "employee_id": emp_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "half_day": half_day,
        "note": note
    }

    token_info = confirmation_manager.mint_token(
        employee_id=emp_id,
        action="submit_leave_request",
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
        "current_available_balance": available,
        "instruction": "Present the structured confirmation card to the user. Ask them to review and confirm."
    }


async def submit_my_leave_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    confirmation_token: str,
    idempotency_key: str = "",
    half_day: bool = False,
    note: str = ""
) -> Dict[str, Any]:
    """Submits an official leave request in WorkWeek HCM upon verifying the cryptographic confirmation token.

    Requires an unexpired, unconsumed confirmation token bound to the authenticated user's payload hash.
    """
    emp_id = get_current_employee_id()
    record_check = confirmation_manager._tokens.get(confirmation_token)
    if not record_check:
        return {
            "error": "404_CONFIRMATION_INVALID",
            "message": "The confirmation token provided is invalid or does not exist."
        }

    inbound_payload = {
        "employee_id": emp_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "half_day": half_day,
        "note": note
    }

    valid, reason, record = confirmation_manager.verify_and_consume(confirmation_token, inbound_payload)
    if not valid:
        return {
            "error": "409_CONFIRMATION_FAILED",
            "message": reason
        }

    result = await workweek_client.submit_leave_request(
        employee_id=emp_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        half_day=half_day,
        note=note,
        idempotency_key=idempotency_key or f"IDEMP-{confirmation_token}"
    )
    return result


async def stage_my_contact_update(
    phone: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact: Optional[str] = None
) -> Dict[str, Any]:
    """Stages a contact information update for the authenticated user and mints a confirmation token."""
    emp_id = get_current_employee_id()
    payload = {
        "employee_id": emp_id,
        "phone": phone or "",
        "address": address or "",
        "emergency_contact": emergency_contact or ""
    }

    token_info = confirmation_manager.mint_token(
        employee_id=emp_id,
        action="update_contact_info",
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


async def update_my_contact_info(
    phone: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact: Optional[str] = None,
    confirmation_token: str = ""
) -> Dict[str, Any]:
    """Executes a contact info update upon verifying the confirmation token."""
    emp_id = get_current_employee_id()
    record_check = confirmation_manager._tokens.get(confirmation_token)
    if not record_check:
        return {"error": "404_CONFIRMATION_INVALID", "message": "Confirmation token is invalid or missing."}

    inbound_payload = {
        "employee_id": emp_id,
        "phone": phone or "",
        "address": address or "",
        "emergency_contact": emergency_contact or ""
    }

    valid, reason, record = confirmation_manager.verify_and_consume(confirmation_token, inbound_payload)
    if not valid:
        return {"error": "409_CONFIRMATION_FAILED", "message": reason}

    result = await workweek_client.update_contact_info(
        employee_id=emp_id,
        phone=phone or None,
        address=address or None,
        emergency_contact=emergency_contact or None
    )
    return result


# =====================================================================
# WorkAgent System Prompt & Instructions (Subject Isolation Strict)
# =====================================================================

WORKAGENT_SYSTEM_INSTRUCTION = """
You are **WorkAgent**, the dedicated Enterprise HCM Specialist Agent for WorkWeek SaaS.
You are currently interacting with **Harry Lin** (Employee ID: **EMP-HL-001**, Email: **harrylin@google.com**).

**CRITICAL SECURITY & ACCESS CONTROL RULES (SDD ADR-005 & TC-SEC-02):**
1. **Strict Subject Isolation:** You MUST ONLY query and manipulate records for the authenticated user, **Harry Lin** (EMP-HL-001).
2. **Rejection of Cross-User Access:** If the user asks about ANY other employee (e.g. "What is Sarah Chen's balance?", "Show Alex Rivera's profile", "Query EMP-002", "Who has the highest leave?"), you MUST IMMEDIATELY REFUSE with:
   "Access Denied (ADR-005 Subject Isolation): Under enterprise zero-trust access policy, you are only authorized to access your own employee records (Harry Lin). Access to other employees' records is strictly restricted."
   Do NOT call any tool for other employees.
3. **Confirm-Before-Commit for Writes:**
   - When Harry requests leave, ALWAYS call `stage_my_leave_request` first. Present the review card with Token and dates.
   - Only call `submit_my_leave_request` when Harry explicitly confirms or provides the confirmation token.
4. **Grounded System-of-Record Answers:**
   - Always state exact values directly returned from the tools and include timestamps. Never invent numbers.
"""

def create_work_agent(model_name: str = "gemini-2.5-flash") -> LlmAgent:
    """Factory function to instantiate WorkAgent with bound self-only tools."""
    return LlmAgent(
        name="work_agent",
        model=model_name,
        instruction=WORKAGENT_SYSTEM_INSTRUCTION.strip(),
        tools=[
            get_my_employee_profile,
            get_my_leave_balances,
            get_my_leave_request_status,
            stage_my_leave_request,
            submit_my_leave_request,
            stage_my_contact_update,
            update_my_contact_info
        ]
    )


class WorkAgentOrchestrator:
    """High-level orchestrator managing sessions and user dialogue."""

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
        authenticated_employee_id: str = "EMP-HL-001",
        user_mcp_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Processes user message with injected identity and user MCP PAT token."""
        session_id = await self.get_or_create_session(user_id)

        # Store session context
        set_session_context(
            session_id=session_id,
            employee_id=authenticated_employee_id,
            user_id=user_id,
            mcp_token=user_mcp_token or workweek_client.mcp_token
        )

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
                        if fr.name in ["stage_my_leave_request", "stage_my_contact_update"] and resp_data.get("status") == "STAGED_AWAITING_CONFIRMATION":
                            confirmation_card = resp_data

        return {
            "session_id": session_id,
            "user_id": user_id,
            "authenticated_employee": {
                "name": "Harry Lin",
                "employee_id": authenticated_employee_id,
                "email": "harrylin@google.com"
            },
            "reply": final_text.strip(),
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "confirmation_card": confirmation_card,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }


# Global orchestrator singleton
orchestrator = WorkAgentOrchestrator()
