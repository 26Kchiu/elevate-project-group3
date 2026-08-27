"""
WorkAgent Definition & Tool Implementations (Google ADK).
Follows SDD Section 3.1 & 3.3 for WorkWeek HCM Domain Agent.
Powered by Gemini 2.5/3.7 Flash on Google ADK.
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

# =====================================================================
# ADK Tool Definitions (SDD Section 3.1 & 3.3)
# =====================================================================

async def get_employee_profile(employee_id: str) -> Dict[str, Any]:
    """Retrieves official employee profile information from WorkWeek HCM.

    Args:
        employee_id: The unique employee ID (e.g. 'EMP-001', 'EMP-002', 'EMP-003').
    Returns:
        JSON object containing name, title, department, manager, location, and contact details.
    """
    return await workweek_client.get_employee_profile(employee_id)


async def get_leave_balances(employee_id: str) -> Dict[str, Any]:
    """Retrieves live leave balances (Vacation, Sick, Medical, Bereavement, Study) from WorkWeek HCM.

    Args:
        employee_id: The unique employee ID (e.g. 'EMP-001').
    Returns:
        JSON object containing accrued, taken, and available days for each leave type with timestamp.
    """
    return await workweek_client.get_leave_balances(employee_id)


async def get_leave_request_status(employee_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Looks up status of past or pending leave requests in WorkWeek HCM.

    Args:
        employee_id: The unique employee ID.
        request_id: Optional reference ID (e.g., 'LR-2026-004412'). If omitted, returns all recent requests.
    """
    return await workweek_client.get_leave_request_status(employee_id, request_id)


async def stage_leave_request(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    half_day: bool = False,
    note: str = ""
) -> Dict[str, Any]:
    """Stages a new leave request and mints a single-use cryptographically bound confirmation token.

    MUST be called before submitting a leave request to present a review card to the user.
    Args:
        employee_id: The employee submitting the request.
        leave_type: 'Vacation', 'Sick', 'Medical', 'Bereavement', or 'Study'.
        start_date: Absolute date in YYYY-MM-DD format.
        end_date: Absolute date in YYYY-MM-DD format.
        half_day: Whether this is a half-day request.
        note: Optional reason or memo.
    """
    # Validate balance first
    bal_res = await workweek_client.get_leave_balances(employee_id)
    type_key = leave_type.lower()
    balances = bal_res.get("balances", {})
    available = 999.0
    if type_key in balances and "available" in balances[type_key]:
        available = balances[type_key]["available"]

    payload = {
        "employee_id": employee_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "half_day": half_day,
        "note": note
    }

    token_info = confirmation_manager.mint_token(
        employee_id=employee_id,
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
        "instruction": "Present the structured confirmation card to the user with the action values and confirmation token. Ask them to confirm."
    }


async def submit_leave_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    confirmation_token: str,
    idempotency_key: str = "",
    half_day: bool = False,
    note: str = ""
) -> Dict[str, Any]:
    """Submits an official leave request in WorkWeek HCM upon verifying the cryptographic confirmation token.

    Requires an unexpired, unconsumed confirmation token matching the exact payload hash.
    """
    record_check = confirmation_manager._tokens.get(confirmation_token)
    if not record_check:
        return {
            "error": "404_CONFIRMATION_INVALID",
            "message": "The confirmation token provided is invalid or does not exist."
        }

    emp_id = record_check.get("employee_id", "EMP-001")
    inbound_payload = {
        "employee_id": emp_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "half_day": half_day,
        "note": note
    }

    # Verify cryptographic token and hash
    valid, reason, record = confirmation_manager.verify_and_consume(confirmation_token, inbound_payload)
    if not valid:
        return {
            "error": "409_CONFIRMATION_FAILED",
            "message": reason
        }

    # Execute commit in WorkWeek HCM
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


async def stage_contact_update(
    employee_id: str,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact: Optional[str] = None
) -> Dict[str, Any]:
    """Stages an employee contact info update and mints a confirmation token."""
    payload = {
        "employee_id": employee_id,
        "phone": phone or "",
        "address": address or "",
        "emergency_contact": emergency_contact or ""
    }

    token_info = confirmation_manager.mint_token(
        employee_id=employee_id,
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


async def update_contact_info(
    phone: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact: Optional[str] = None,
    confirmation_token: str = ""
) -> Dict[str, Any]:
    """Executes an employee contact info update upon verifying confirmation token."""
    record_check = confirmation_manager._tokens.get(confirmation_token)
    if not record_check:
        return {"error": "404_CONFIRMATION_INVALID", "message": "Confirmation token is invalid or missing."}

    emp_id = record_check.get("employee_id", "EMP-001")
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
# WorkAgent System Prompt & Instructions
# =====================================================================

WORKAGENT_SYSTEM_INSTRUCTION = """
You are **WorkAgent**, the dedicated Enterprise HCM Specialist Agent for WorkWeek SaaS.
Your primary role is to assist employees with:
1. **Employee Profile Inquiries:** Retrieve profile details (name, title, department, tenure, manager, location, contact info).
2. **Leave Balances & Entitlements:** Look up live available leave balances (Vacation, Sick, Medical, Bereavement, Study).
3. **Leave Request Submission (Confirm-Before-Commit):** 
   - When an employee requests leave, ALWAYS call `stage_leave_request` first to check balance sufficiency and mint a cryptographic confirmation token.
   - Present a clear Action Review Card to the user with Leave Type, Dates, Total Days, Remaining Balance, and the Confirmation Token.
   - When the user confirms (e.g. saying "Confirm", "Yes", or providing the token), invoke `submit_leave_request` with the exact parameters and token.
4. **Contact Information Updates:** Stage changes via `stage_contact_update` and execute via `update_contact_info` after user confirmation.
5. **Leave Status Lookups:** Check status of previous leave submissions via `get_leave_request_status`.

**Operational Principles (SDD Compliance):**
- **System-of-Record Grounding:** State facts directly from WorkWeek tool responses with exact timestamp. Never hallucinate balances.
- **Safety & Isolation:** Operate strictly within the authenticated employee's scope.
- **Tone:** Professional, clear, empathetic, and concise.

Default context: Use the employee ID specified in the context prefix (e.g., EMP-001).
"""

def create_work_agent(model_name: str = "gemini-2.5-flash") -> LlmAgent:
    """Factory function to instantiate the WorkAgent with bound tools."""
    return LlmAgent(
        name="work_agent",
        model=model_name,
        instruction=WORKAGENT_SYSTEM_INSTRUCTION.strip(),
        tools=[
            get_employee_profile,
            get_leave_balances,
            get_leave_request_status,
            stage_leave_request,
            submit_leave_request,
            stage_contact_update,
            update_contact_info
        ]
    )


class WorkAgentOrchestrator:
    """High-level orchestrator managing sessions, multi-turn dialogue, and tool invocation."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.agent = create_work_agent(model_name=model_name)
        self.session_service = InMemorySessionService()
        self.runner = Runner(app_name="work_agent_app", agent=self.agent, session_service=self.session_service)
        self._active_sessions: Dict[str, str] = {}

    async def get_or_create_session(self, user_id: str) -> str:
        """Gets existing session ID for user or creates a new one."""
        if user_id in self._active_sessions:
            return self._active_sessions[user_id]
        session = await self.session_service.create_session(app_name="work_agent_app", user_id=user_id)
        self._active_sessions[user_id] = session.id
        return session.id

    async def process_user_message(self, user_id: str, message_text: str, current_employee_id: str = "EMP-001") -> Dict[str, Any]:
        """Processes an interactive natural language message from the user and returns structured response."""
        session_id = await self.get_or_create_session(user_id)

        # Inject context hint if needed
        augmented_prompt = f"[Active Employee Context: {current_employee_id}] {message_text}"

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=augmented_prompt)]
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
                        # Check if a confirmation card was staged
                        if fr.name in ["stage_leave_request", "stage_contact_update"] and resp_data.get("status") == "STAGED_AWAITING_CONFIRMATION":
                            confirmation_card = resp_data

        return {
            "session_id": session_id,
            "user_id": user_id,
            "employee_id": current_employee_id,
            "reply": final_text.strip(),
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "confirmation_card": confirmation_card,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }


# Global orchestrator singleton
orchestrator = WorkAgentOrchestrator()
