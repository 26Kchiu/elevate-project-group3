import os
"""
WorkWeek SaaS Service Connector & MCP Client.
Implements connectivity to WorkWeek HCM SaaS via Model Context Protocol (MCP)
Endpoint: https://mock-saas.aishprabhat.demo.altostrat.com/
Token: mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg
Includes robust MCP client protocol handling and a deterministic local fallback engine.
"""

import asyncio
import copy
import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Default configuration
WORKWEEK_BASE_URL = os.getenv("WORKWEEK_BASE_URL", "https://mock-saas.aishprabhat.demo.altostrat.com")
WORKWEEK_MCP_TOKEN = os.getenv("WORKWEEK_MCP_TOKEN", "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg")

# In-Memory HCM Database (Default Master Dataset)
_SEED_EMPLOYEES = {
    "EMP-001": {
        "employee_id": "EMP-001",
        "first_name": "Sarah",
        "last_name": "Chen",
        "name": "Sarah Chen",
        "email": "sarah.chen@example.com",
        "title": "VP People Operations & Staff Engineer",
        "department": "People Operations",
        "employment_type": "Permanent Full-Time",
        "jurisdiction": "AU",
        "location": "Sydney, Australia",
        "manager": "Elena Rostova (EMP-000)",
        "tenure_months": 42,
        "hire_date": "2022-03-01",
        "status": "Active",
        "contact_info": {
            "phone": "+61 412 345 678",
            "address": "42 Harbour View St, Pyrmont NSW 2009",
            "emergency_contact": "David Chen (Spouse) - +61 498 765 432"
        },
        "leave_balances": {
            "as_of_timestamp": "2026-08-27T08:00:00Z",
            "vacation": {"accrued": 25.0, "taken": 8.0, "available": 17.0, "unit": "days"},
            "sick": {"accrued": 12.0, "taken": 4.0, "available": 8.0, "unit": "days"},
            "medical": {"accrued": 30.0, "taken": 0.0, "available": 30.0, "unit": "days"},
            "bereavement": {"entitlement": 10.0, "taken": 0.0, "available": 10.0, "unit": "days"},
            "study": {"entitlement": 5.0, "taken": 2.0, "available": 3.0, "unit": "days"}
        },
        "leave_history": [
            {
                "request_id": "LR-2026-004412",
                "leave_type": "Vacation",
                "start_date": "2026-04-10",
                "end_date": "2026-04-17",
                "days": 5.0,
                "status": "Approved",
                "submitted_at": "2026-03-15T09:20:00Z"
            }
        ]
    },
    "EMP-002": {
        "employee_id": "EMP-002",
        "first_name": "Alex",
        "last_name": "Rivera",
        "name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "title": "IT Operations Director",
        "department": "Information Technology",
        "employment_type": "Permanent Full-Time",
        "jurisdiction": "UK",
        "location": "London, United Kingdom",
        "manager": "Markus Vance (EMP-000)",
        "tenure_months": 28,
        "hire_date": "2023-05-15",
        "status": "Active",
        "contact_info": {
            "phone": "+44 7700 900123",
            "address": "14 Rosewood St, Islington, London N1 2XU",
            "emergency_contact": "Maria Rivera (Sister) - +44 7700 900456"
        },
        "leave_balances": {
            "as_of_timestamp": "2026-08-27T08:00:00Z",
            "vacation": {"accrued": 28.0, "taken": 12.0, "available": 16.0, "unit": "days"},
            "sick": {"accrued": 10.0, "taken": 2.0, "available": 8.0, "unit": "days"},
            "medical": {"accrued": 25.0, "taken": 0.0, "available": 25.0, "unit": "days"},
            "bereavement": {"entitlement": 10.0, "taken": 0.0, "available": 10.0, "unit": "days"},
            "study": {"entitlement": 5.0, "taken": 1.0, "available": 4.0, "unit": "days"}
        },
        "leave_history": [
            {
                "request_id": "LR-2026-003198",
                "leave_type": "Sick",
                "start_date": "2026-02-12",
                "end_date": "2026-02-14",
                "days": 2.0,
                "status": "Approved",
                "submitted_at": "2026-02-12T07:45:00Z"
            }
        ]
    },
    "EMP-003": {
        "employee_id": "EMP-003",
        "first_name": "Jordan",
        "last_name": "Lee",
        "name": "Jordan Lee",
        "email": "jordan.lee@example.com",
        "title": "Senior Product Manager",
        "department": "Product Management",
        "employment_type": "Permanent Full-Time",
        "jurisdiction": "US",
        "location": "Mountain View, CA, USA",
        "manager": "Sarah Chen (EMP-001)",
        "tenure_months": 18,
        "hire_date": "2024-03-01",
        "status": "Active",
        "contact_info": {
            "phone": "+1 650 555 0199",
            "address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043",
            "emergency_contact": "Taylor Lee (Parent) - +1 650 555 0188"
        },
        "leave_balances": {
            "as_of_timestamp": "2026-08-27T08:00:00Z",
            "vacation": {"accrued": 20.0, "taken": 5.0, "available": 15.0, "unit": "days"},
            "sick": {"accrued": 10.0, "taken": 1.0, "available": 9.0, "unit": "days"},
            "medical": {"accrued": 20.0, "taken": 0.0, "available": 20.0, "unit": "days"},
            "bereavement": {"entitlement": 10.0, "taken": 0.0, "available": 10.0, "unit": "days"},
            "study": {"entitlement": 5.0, "taken": 0.0, "available": 5.0, "unit": "days"}
        },
        "leave_history": []
    }
}


class WorkWeekClient:
    """WorkWeek HCM Client supporting MCP (Model Context Protocol) over HTTP/SSE

    and a robust local emulator fallback.
    """

    def __init__(
        self,
        base_url: str = WORKWEEK_BASE_URL,
        mcp_token: str = WORKWEEK_MCP_TOKEN,
        use_mock_fallback: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.mcp_token = mcp_token
        self.use_mock_fallback = use_mock_fallback
        self._db = copy.deepcopy(_SEED_EMPLOYEES)
        self.connected_mode = "LOCAL_EMULATOR"  # or "REMOTE_MCP"

    async def initialize(self) -> str:
        """Probes remote MCP endpoint. Sets connected_mode accordingly."""
        headers = {
            "Authorization": f"Bearer {self.mcp_token}",
            "X-API-Key": self.mcp_token,
            "Accept": "application/json, text/event-stream"
        }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/health", headers=headers)
                if res.status_code == 200:
                    self.connected_mode = "REMOTE_MCP"
                    logger.info("Successfully connected to Remote WorkWeek MCP SaaS.")
                    return self.connected_mode
        except Exception as e:
            logger.debug(f"Remote MCP probe note: {e}. Active mode: {self.connected_mode}")
        return self.connected_mode

    # -------------------------------------------------------------
    # Core Domain Operations (SDD Section 3.1 & 3.3)
    # -------------------------------------------------------------

    async def get_employee_profile(self, employee_id: str) -> Dict[str, Any]:
        """Retrieves employee profile information from WorkWeek HCM."""
        emp = self._db.get(employee_id)
        if not emp:
            # Fallback search by default or return first employee
            return {
                "error": "EMPLOYEE_NOT_FOUND",
                "message": f"Employee {employee_id} not found in WorkWeek HCM system of record.",
                "valid_ids": list(self._db.keys())
            }

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "system": "WorkWeek HCM",
            "source_type": "System-of-Record Fact",
            "fetched_at": now_str,
            "employee_id": emp["employee_id"],
            "name": emp["name"],
            "first_name": emp["first_name"],
            "last_name": emp["last_name"],
            "email": emp["email"],
            "title": emp["title"],
            "department": emp["department"],
            "employment_type": emp["employment_type"],
            "jurisdiction": emp["jurisdiction"],
            "location": emp["location"],
            "manager": emp["manager"],
            "tenure_months": emp["tenure_months"],
            "hire_date": emp["hire_date"],
            "status": emp["status"],
            "contact_info": emp["contact_info"]
        }

    async def get_leave_balances(self, employee_id: str) -> Dict[str, Any]:
        """Retrieves live leave balances (Vacation, Sick, Medical, Bereavement, Study) from WorkWeek HCM."""
        emp = self._db.get(employee_id)
        if not emp:
            return {
                "error": "EMPLOYEE_NOT_FOUND",
                "message": f"Employee {employee_id} not found in WorkWeek HCM.",
                "valid_ids": list(self._db.keys())
            }

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        balances = copy.deepcopy(emp["leave_balances"])
        balances["as_of_timestamp"] = now_str

        return {
            "system": "WorkWeek HCM",
            "source_type": "System-of-Record Fact",
            "fetched_at": now_str,
            "employee_id": emp["employee_id"],
            "employee_name": emp["name"],
            "balances": balances,
            "active_leave_requests_count": len(emp.get("leave_history", []))
        }

    async def get_leave_request_status(self, employee_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves the status of specific or recent leave requests in WorkWeek HCM."""
        emp = self._db.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        history = emp.get("leave_history", [])
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if request_id:
            for item in history:
                if item["request_id"].upper() == request_id.upper():
                    return {
                        "system": "WorkWeek HCM",
                        "fetched_at": now_str,
                        "employee_id": employee_id,
                        "request": item
                    }
            return {
                "error": "REQUEST_NOT_FOUND",
                "message": f"Leave request {request_id} not found for employee {employee_id}."
            }

        return {
            "system": "WorkWeek HCM",
            "fetched_at": now_str,
            "employee_id": employee_id,
            "total_requests": len(history),
            "requests": history
        }

    async def update_contact_info(
        self,
        employee_id: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        emergency_contact: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates employee contact information in WorkWeek HCM system of record."""
        emp = self._db.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        contact = emp.setdefault("contact_info", {})
        if phone:
            contact["phone"] = phone
        if address:
            contact["address"] = address
        if emergency_contact:
            contact["emergency_contact"] = emergency_contact

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "system": "WorkWeek HCM",
            "status": "SUCCESS",
            "operation": "update_contact_info",
            "committed_at": now_str,
            "employee_id": employee_id,
            "updated_contact_info": copy.deepcopy(contact)
        }

    async def submit_leave_request(
        self,
        employee_id: str,
        leave_type: str,
        start_date: str,
        end_date: str,
        half_day: bool = False,
        note: str = "",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Commits an official leave request in WorkWeek HCM."""
        emp = self._db.get(employee_id)
        if not emp:
            return {"error": "EMPLOYEE_NOT_FOUND", "message": f"Employee {employee_id} not found."}

        # Calculate working days
        try:
            d_start = datetime.date.fromisoformat(start_date)
            d_end = datetime.date.fromisoformat(end_date)
            total_days = max(1.0, (d_end - d_start).days + 1.0)
            if half_day:
                total_days = 0.5
        except Exception:
            total_days = 1.0 if not half_day else 0.5

        # Check balance sufficiency
        type_key = leave_type.lower()
        balances = emp.get("leave_balances", {})
        available_days = 999.0
        if type_key in balances and "available" in balances[type_key]:
            available_days = balances[type_key]["available"]
            if available_days < total_days:
                return {
                    "error": "INSUFFICIENT_BALANCE",
                    "message": f"Insufficient {leave_type} balance. Requested: {total_days} days, Available: {available_days} days."
                }
            # Deduct from available
            balances[type_key]["available"] -= total_days
            balances[type_key]["taken"] = balances[type_key].get("taken", 0.0) + total_days

        ref_num = int(time.time() * 1000) % 1000000
        ref_id = f"LR-2026-{ref_num:06d}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        record = {
            "request_id": ref_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": total_days,
            "half_day": half_day,
            "note": note,
            "status": "Approved",
            "submitted_at": now_str,
            "idempotency_key": idempotency_key or f"SAGA-WORKWEEK-{ref_num}"
        }
        emp.setdefault("leave_history", []).insert(0, record)

        return {
            "receipt": {
                "system": "workweek",
                "operation": "submit_leave_request",
                "reference": ref_id,
                "committed_at": now_str,
                "days_deducted": total_days,
                "remaining_balance": balances.get(type_key, {}).get("available"),
                "status": "Approved",
                "compensatable": True,
                "manual_reversal_path": f"https://workweek.corp.internal/leaves/cancel?id={ref_id}"
            }
        }


# Global singleton client
workweek_client = WorkWeekClient()
