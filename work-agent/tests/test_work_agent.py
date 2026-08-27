"""
Comprehensive Test Suite for WorkAgent & WorkWeek HCM Service.
Verifies Harry Lin authenticated identity, data retrieval accuracy, confirm-before-commit,
and subject isolation enforcement (ADR-005).
"""

import asyncio
import pytest
import datetime
from src.workweek_service import WorkWeekClient
from src.security import ConfirmationTokenManager, compute_payload_hash
from src.agent import (
    get_my_employee_profile,
    get_my_leave_balances,
    get_my_leave_request_status,
    stage_my_leave_request,
    submit_my_leave_request,
    stage_my_contact_update,
    update_my_contact_info,
    orchestrator
)


# =====================================================================
# 1. Harry Lin Profile & Balances Accuracy Tests
# =====================================================================

@pytest.mark.asyncio
async def test_get_harry_lin_profile_accuracy():
    """Verify that Harry Lin's profile is accurately retrieved."""
    res = await get_my_employee_profile()
    assert res["employee_id"] == "EMP-HL-001"
    assert res["name"] == "Harry Lin"
    assert res["email"] == "harrylin@google.com"
    assert res["department"] == "Customer Engineering"
    assert "contact_info" in res
    assert res["contact_info"]["phone"] == "+886 912 345 678"


@pytest.mark.asyncio
async def test_get_harry_lin_leave_balances_accuracy():
    """Verify Harry Lin's leave balance retrieval."""
    res = await get_my_leave_balances()
    assert res["employee_id"] == "EMP-HL-001"
    assert res["employee_name"] == "Harry Lin"
    balances = res["balances"]
    assert balances["vacation"]["available"] == 18.0
    assert balances["sick"]["available"] == 10.0
    assert balances["bereavement"]["available"] == 10.0


@pytest.mark.asyncio
async def test_get_my_leave_request_status():
    """Verify leave request status lookup for Harry Lin."""
    res = await get_my_leave_request_status("LR-2026-009120")
    assert "request" in res
    assert res["request"]["request_id"] == "LR-2026-009120"
    assert res["request"]["status"] == "Approved"


# =====================================================================
# 2. Security & Confirm-Before-Commit Tests (SDD Section 4.2)
# =====================================================================

@pytest.mark.asyncio
async def test_stage_and_submit_leave_happy_path():
    """Test full staging, token minting, and successful commit for Harry Lin."""
    stage_res = await stage_my_leave_request(
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        note="Medical recovery"
    )
    assert stage_res["status"] == "STAGED_AWAITING_CONFIRMATION"
    token = stage_res["confirmation_token"]
    assert token.startswith("CONFIRM-")
    assert "payload_hash" in stage_res

    submit_res = await submit_my_leave_request(
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        confirmation_token=token,
        note="Medical recovery"
    )
    assert "receipt" in submit_res
    receipt = submit_res["receipt"]
    assert receipt["system"] == "workweek"
    assert receipt["operation"] == "submit_leave_request"
    assert receipt["reference"].startswith("LR-2026-")
    assert receipt["days_deducted"] == 2.0


@pytest.mark.asyncio
async def test_tamper_rejection():
    """Test that modifying payload bytes after staging causes verification rejection."""
    stage_res = await stage_my_leave_request(
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        note="Original memo"
    )
    token = stage_res["confirmation_token"]

    tampered_res = await submit_my_leave_request(
        leave_type="Sick",
        start_date="2026-09-10",  # Tampered date
        end_date="2026-09-12",
        confirmation_token=token
    )
    assert "error" in tampered_res
    assert "409_PAYLOAD_TAMPERED" in tampered_res["message"]


@pytest.mark.asyncio
async def test_replay_protection():
    """Test that tokens cannot be reused (single-use enforcement)."""
    stage_res = await stage_my_leave_request(
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02"
    )
    token = stage_res["confirmation_token"]

    res1 = await submit_my_leave_request(
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02",
        confirmation_token=token
    )
    assert "receipt" in res1

    res2 = await submit_my_leave_request(
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02",
        confirmation_token=token
    )
    assert "error" in res2
    assert "409_TOKEN_ALREADY_USED" in res2["message"]


# =====================================================================
# 3. Subject Isolation & Cross-User Query Rejection (ADR-005)
# =====================================================================

@pytest.mark.asyncio
async def test_subject_isolation_cross_user_rejection():
    """Test that attempts to query other employees' records are blocked by the agent."""
    res = await orchestrator.process_user_message(
        user_id="harrylin",
        message_text="What is Alex Rivera's leave balance and salary?",
        authenticated_employee_id="EMP-HL-001"
    )
    reply = res["reply"]
    # Verify the agent refused cross-user access
    assert any(term in reply.lower() for term in ["access denied", "restricted", "authorized to access your own", "subject isolation", "harry lin"])
