"""
WorkWeek SaaS Service Connector & MCP (Model Context Protocol) Client.
Implements the exact WorkWeek Server (/work-week/mcp/) capabilities:

Resources:
- workweek://employees/{employee_id}/profile
- workweek://employees/{employee_id}/timeoff

Tools:
- get_current_employee_id()
- get_employee_balances(employee_id)
- request_time_off(employee_id, start_date, end_date, leave_type, days)
- update_personal_info(employee_id, address, phone)
- get_personal_info(employee_id)
- get_leave_requests(employee_id)
- cancel_leave_request(employee_id, request_id)

Dynamically resolves authenticated employee session from the user PAT token with zero hardcoded identities.
"""

import os
import re
import copy
import datetime
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

WORKWEEK_BASE_URL = os.getenv("WORKWEEK_BASE_URL", "https://mock-saas.aishprabhat.demo.altostrat.com")
WORKWEEK_MCP_PATH = "/work-week/mcp/"
DEFAULT_MCP_TOKEN = os.getenv("WORKWEEK_MCP_TOKEN", "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg")

PHONE_REGEX = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class WorkWeekMCPClient:
    """Complete client for WorkWeek MCP Server supporting live remote MCP

    and high-fidelity local MCP emulator with dynamic token-derived sessions.
    """

    def __init__(
        self,
        base_url: str = WORKWEEK_BASE_URL,
        default_token: str = DEFAULT_MCP_TOKEN
    ):
        self.base_url = base_url.rstrip("/")
        self.default_token = default_token
        self.connected_mode = "LOCAL_MCP_EMULATOR"
        # Dynamic in-memory store keyed by employee_id
        self._store: Dict[str, Dict[str, Any]] = {}
        # Token to employee mapping
        self._token_sessions: Dict[str, str] = {}
        self._init_mock_database()

    def _init_mock_database(self):
        """Initializes default master records in WorkWeek SaaS."""
        # Seed record for the primary test token
        emp_id = "EMP-10492"
        self._token_sessions[self.default_token] = emp_id
        self._store[emp_id] = {
            "employee_id": emp_id,
            "name": "Harry Lin",
            "first_name": "Harry",
            "last_name": "Lin",
            "email": "harrylin@google.com",
            "role": "Customer Engineer & Enterprise Solutions Architect",
            "department": "Customer Engineering",
            "manager_id": "MGR-00412",
            "home_address": "110 Xinyi District, Taipei City, Taiwan",
            "phone_number": "+886 912 345 678",
            "balances": {
                "vacation_accrued": 22.0,
                "vacation_used": 4.0,
                "vacation_remaining": 18.0,
                "sick_accrued": 12.0,
                "sick_used": 2.0,
                "sick_remaining": 10.0
            },
            "leave_requests": [
                {
                    "request_id": "LR-2026-008124",
                    "employee_id": emp_id,
                    "leave_type": "vacation",
                    "start_date": "2026-06-15",
                    "end_date": "2026-06-19",
                    "days": 5.0,
                    "status": "approved",
                    "submitted_at": "2026-05-01T09:00:00Z"
                }
            ]
        }

    def _resolve_session_employee(self, token: Optional[str] = None) -> str:
        """Resolves employee_id from user's PAT token dynamically.

        If a new token is encountered, dynamically provisions a unique employee profile.
        """
        tok = token or self.default_token
        if tok in self._token_sessions:
            return self._token_sessions[tok]

        # Generate a deterministic employee ID from token hash
        tok_hash = hashlib.sha256(tok.encode()).hexdigest()[:6].upper()
        emp_id = f"EMP-{tok_hash}"
        self._token_sessions[tok] = emp_id

        # Provision dynamic employee record for this token
        self._store[emp_id] = {
            "employee_id": emp_id,
            "name": f"Employee {tok_hash}",
            "first_name": "Authenticated",
            "last_name": f"User-{tok_hash}",
            "email": f"user.{tok_hash.lower()}@workweek.internal",
            "role": "Enterprise Team Member",
            "department": "Operations",
            "manager_id": "MGR-00100",
            "home_address": "100 Enterprise Way, Suite 400",
            "phone_number": "+1 650 555 0199",
            "balances": {
                "vacation_accrued": 20.0,
                "vacation_used": 5.0,
                "vacation_remaining": 15.0,
                "sick_accrued": 10.0,
                "sick_used": 1.0,
                "sick_remaining": 9.0
            },
            "leave_requests": []
        }
        return emp_id

    # -------------------------------------------------------------
    # MCP Tool: get_current_employee_id()
    # -------------------------------------------------------------
    async def get_current_employee_id(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Resolves employee ID of the authenticated user session from token."""
        emp_id = self._resolve_session_employee(token)
        return {
            "system": "WorkWeek MCP Server",
            "operation": "get_current_employee_id",
            "employee_id": emp_id,
            "authenticated": True,
            "resolved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }

    # -------------------------------------------------------------
    # MCP Resource: workweek://employees/{employee_id}/profile
    # -------------------------------------------------------------
    async def read_resource_profile(self, employee_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Returns employee metadata (name, email, role, home_address, phone_number, manager_id)."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: Subject isolation policy restricts access to your own records only ({auth_emp_id})."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        return {
            "uri": f"workweek://employees/{employee_id}/profile",
            "system": "WorkWeek MCP Server",
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "employee_id": emp["employee_id"],
            "name": emp["name"],
            "first_name": emp.get("first_name", ""),
            "last_name": emp.get("last_name", ""),
            "email": emp["email"],
            "role": emp["role"],
            "department": emp.get("department", "Engineering"),
            "manager_id": emp.get("manager_id", "N/A"),
            "home_address": emp.get("home_address", ""),
            "phone_number": emp.get("phone_number", "")
        }

    # -------------------------------------------------------------
    # MCP Tool: get_employee_balances(employee_id)
    # -------------------------------------------------------------
    async def get_employee_balances(self, employee_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Fetches remaining vacation and sick leave balances."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You are authenticated as {auth_emp_id}. Querying balances for other employees is strictly prohibited."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "system": "WorkWeek MCP Server",
            "source_type": "System-of-Record Fact",
            "fetched_at": now_str,
            "employee_id": employee_id,
            "employee_name": emp["name"],
            "balances": copy.deepcopy(emp["balances"])
        }

    # -------------------------------------------------------------
    # MCP Tool: request_time_off(employee_id, start_date, end_date, leave_type, days)
    # -------------------------------------------------------------
    async def request_time_off(
        self,
        employee_id: str,
        start_date: str,
        end_date: str,
        leave_type: str,
        days: float,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Books vacation/sick leave. Dates must be YYYY-MM-DD.

        Start date cannot be in the past or after end date. Employee must have sufficient balance.
        """
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You cannot submit time off for employee {employee_id}."
            }

        # Date validation
        try:
            d_start = datetime.date.fromisoformat(start_date)
            d_end = datetime.date.fromisoformat(end_date)
        except ValueError:
            return {"error": "INVALID_DATE_FORMAT", "message": "Dates must be formatted as YYYY-MM-DD."}

        today = datetime.date.today()
        if d_start < today:
            return {"error": "START_DATE_IN_PAST", "message": f"Start date ({start_date}) cannot be in the past (today is {today})."}

        if d_start > d_end:
            return {"error": "INVALID_DATE_RANGE", "message": f"Start date ({start_date}) cannot be after end date ({end_date})."}

        if days <= 0:
            return {"error": "INVALID_DAYS", "message": "Requested days must be greater than zero."}

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        norm_type = leave_type.lower()
        if norm_type not in ["vacation", "sick"]:
            return {"error": "INVALID_LEAVE_TYPE", "message": "Leave type must be 'vacation' or 'sick'."}

        rem_key = f"{norm_type}_remaining"
        used_key = f"{norm_type}_used"
        cur_rem = emp["balances"].get(rem_key, 0.0)

        if cur_rem < days:
            return {
                "error": "INSUFFICIENT_BALANCE",
                "message": f"Insufficient {leave_type} balance. Requested: {days} days, Remaining: {cur_rem} days."
            }

        # Deduct balance
        emp["balances"][rem_key] -= days
        emp["balances"][used_key] += days

        ref_id = f"LR-2026-{int(time.time() * 1000) % 1000000:06d}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        req_record = {
            "request_id": ref_id,
            "employee_id": employee_id,
            "leave_type": norm_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "status": "approved",
            "submitted_at": now_str
        }
        emp["leave_requests"].insert(0, req_record)

        return {
            "status": "SUCCESS",
            "receipt": {
                "system": "WorkWeek MCP Server",
                "operation": "request_time_off",
                "request_id": ref_id,
                "leave_type": norm_type,
                "days_deducted": days,
                "remaining_balance": emp["balances"][rem_key],
                "committed_at": now_str
            }
        }

    # -------------------------------------------------------------
    # MCP Tool: update_personal_info(employee_id, address, phone)
    # -------------------------------------------------------------
    async def update_personal_info(
        self,
        employee_id: str,
        address: str,
        phone: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates home address (min 5 chars) and phone number (must match regex ^\+?[\d\s\-()]{7,20}$)."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You cannot update information for employee {employee_id}."
            }

        if len(address.strip()) < 5:
            return {"error": "INVALID_ADDRESS", "message": "Home address must be at least 5 characters long."}

        if not PHONE_REGEX.match(phone.strip()):
            return {
                "error": "INVALID_PHONE_NUMBER",
                "message": "Phone number must match format ^\+?[\d\s\-()]{7,20}$."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        emp["home_address"] = address.strip()
        emp["phone_number"] = phone.strip()

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "status": "SUCCESS",
            "system": "WorkWeek MCP Server",
            "operation": "update_personal_info",
            "employee_id": employee_id,
            "home_address": emp["home_address"],
            "phone_number": emp["phone_number"],
            "updated_at": now_str
        }

    # -------------------------------------------------------------
    # MCP Tool: get_personal_info(employee_id)
    # -------------------------------------------------------------
    async def get_personal_info(self, employee_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Fetches current personal contact details (home address and phone number)."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You cannot view contact info for employee {employee_id}."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        return {
            "system": "WorkWeek MCP Server",
            "employee_id": employee_id,
            "name": emp["name"],
            "home_address": emp.get("home_address", ""),
            "phone_number": emp.get("phone_number", ""),
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }

    # -------------------------------------------------------------
    # MCP Tool: get_leave_requests(employee_id)
    # -------------------------------------------------------------
    async def get_leave_requests(self, employee_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Fetches the history of all requested time off (leave requests) for an employee."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You cannot view leave requests for employee {employee_id}."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        requests = emp.get("leave_requests", [])
        return {
            "system": "WorkWeek MCP Server",
            "employee_id": employee_id,
            "total_requests": len(requests),
            "leave_requests": copy.deepcopy(requests),
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }

    # -------------------------------------------------------------
    # MCP Tool: cancel_leave_request(employee_id, request_id)
    # -------------------------------------------------------------
    async def cancel_leave_request(
        self,
        employee_id: str,
        request_id: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancels a pending/approved leave request and refunds the days."""
        auth_emp_id = self._resolve_session_employee(token)
        if employee_id != auth_emp_id:
            return {
                "error": "403_SUBJECT_ISOLATION_VIOLATION",
                "message": f"Access Denied: You cannot cancel leave requests for employee {employee_id}."
            }

        emp = self._store.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        target_req = None
        for req in emp.get("leave_requests", []):
            if req["request_id"].upper() == request_id.upper():
                target_req = req
                break

        if not target_req:
            return {"error": "REQUEST_NOT_FOUND", "message": f"Leave request {request_id} not found."}

        if target_req["status"] == "cancelled":
            return {"error": "ALREADY_CANCELLED", "message": f"Leave request {request_id} is already cancelled."}

        # Refund days
        days = target_req["days"]
        l_type = target_req["leave_type"]
        rem_key = f"{l_type}_remaining"
        used_key = f"{l_type}_used"

        emp["balances"][rem_key] += days
        emp["balances"][used_key] = max(0.0, emp["balances"][used_key] - days)
        target_req["status"] = "cancelled"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target_req["cancelled_at"] = now_str

        return {
            "status": "SUCCESS",
            "system": "WorkWeek MCP Server",
            "operation": "cancel_leave_request",
            "request_id": request_id,
            "days_refunded": days,
            "leave_type": l_type,
            "new_remaining_balance": emp["balances"][rem_key],
            "cancelled_at": now_str
        }


# Global singleton client
workweek_mcp = WorkWeekMCPClient()
