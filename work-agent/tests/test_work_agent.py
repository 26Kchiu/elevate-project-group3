"""
Comprehensive Test Suite for WorkAgent & WorkWeek HCM Service.
Verifies data retrieval accuracy, confirm-before-commit security, and interactive flows.
"""

import asyncio
import pytest
import datetime
from src.workweek_service import WorkWeekClient
from src.security import ConfirmationTokenManager, compute_payload_hash
from src.agent import (
    get_employee_profile,
    get_leave_balances,
    get_leave_request_status,
    stage_leave_request,
    submit_leave_request,
    stage_contact_update,
    update_contact_info,
    orchestrator
)


@pytest.fixture
def client():
    return WorkWeekClient(use_mock_fallback=True)


@pytest.fixture
def token_mgr():
    return ConfirmationTokenManager(default_ttl_seconds=300)


# =====================================================================
# 1. Data Retrieval Accuracy Tests
# =====================================================================

@pytest.mark.asyncio
async def test_get_employee_profile_accuracy():
    """Verify that employee profile data retrieved matches WorkWeek records."""
    res = await get_employee_profile("EMP-001")
    assert res["employee_id"] == "EMP-001"
    assert res["name"] == "Sarah Chen"
    assert res["department"] == "People Operations"
    assert res["jurisdiction"] == "AU"
    assert res["tenure_months"] == 42
    assert "contact_info" in res
    assert res["contact_info"]["phone"] == "+61 412 345 678"

    # Test Alex Rivera EMP-002
    res2 = await get_employee_profile("EMP-002")
    assert res2["employee_id"] == "EMP-002"
    assert res2["name"] == "Alex Rivera"
    assert res2["jurisdiction"] == "UK"


@pytest.mark.asyncio
async def test_get_leave_balances_accuracy():
    """Verify leave balance retrieval for all policy types."""
    res = await get_leave_balances("EMP-001")
    assert res["employee_id"] == "EMP-001"
    balances = res["balances"]
    assert "vacation" in balances
    assert "sick" in balances
    assert "medical" in balances
    assert "bereavement" in balances
    assert "study" in balances

    # Check exact values
    assert balances["vacation"]["available"] == 17.0
    assert balances["sick"]["available"] == 8.0
    assert balances["bereavement"]["available"] == 10.0


@pytest.mark.asyncio
async def test_get_leave_request_status():
    """Verify leave request status lookup."""
    res = await get_leave_request_status("EMP-001", "LR-2026-004412")
    assert "request" in res
    assert res["request"]["request_id"] == "LR-2026-004412"
    assert res["request"]["status"] == "Approved"


# =====================================================================
# 2. Security & Confirm-Before-Commit Tests (SDD Section 4.2)
# =====================================================================

@pytest.mark.asyncio
async def test_stage_and_submit_leave_happy_path():
    """Test full staging, token minting, and successful commit."""
    # 1. Stage leave request
    stage_res = await stage_leave_request(
        employee_id="EMP-001",
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        note="Doctor appointment"
    )
    assert stage_res["status"] == "STAGED_AWAITING_CONFIRMATION"
    token = stage_res["confirmation_token"]
    assert token.startswith("CONFIRM-")
    assert "payload_hash" in stage_res

    # 2. Submit with valid token
    submit_res = await submit_leave_request(
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        confirmation_token=token,
        note="Doctor appointment"
    )
    assert "receipt" in submit_res
    receipt = submit_res["receipt"]
    assert receipt["system"] == "workweek"
    assert receipt["operation"] == "submit_leave_request"
    assert receipt["reference"].startswith("LR-2026-")
    assert receipt["days_deducted"] == 2.0
    assert receipt["status"] == "Approved"


@pytest.mark.asyncio
async def test_tamper_rejection():
    """Test that modifying payload bytes after staging causes verification rejection."""
    stage_res = await stage_leave_request(
        employee_id="EMP-001",
        leave_type="Sick",
        start_date="2026-09-01",
        end_date="2026-09-02",
        note="Original memo"
    )
    token = stage_res["confirmation_token"]

    # Inbound tries to change date to 2026-09-10 without re-minting
    tampered_res = await submit_leave_request(
        leave_type="Sick",
        start_date="2026-09-10",  # TAMPERED
        end_date="2026-09-12",
        confirmation_token=token
    )
    assert "error" in tampered_res
    assert "409_PAYLOAD_TAMPERED" in tampered_res["message"]


@pytest.mark.asyncio
async def test_replay_protection():
    """Test that tokens cannot be reused (single-use enforcement)."""
    stage_res = await stage_leave_request(
        employee_id="EMP-002",
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02"
    )
    token = stage_res["confirmation_token"]

    # First submit succeeds
    res1 = await submit_leave_request(
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02",
        confirmation_token=token
    )
    assert "receipt" in res1

    # Second submit with same token is rejected
    res2 = await submit_leave_request(
        leave_type="Vacation",
        start_date="2026-11-01",
        end_date="2026-11-02",
        confirmation_token=token
    )
    assert "error" in res2
    assert "409_TOKEN_ALREADY_USED" in res2["message"]


@pytest.mark.asyncio
async def test_insufficient_balance_handling():
    """Test that requesting more days than available balance is blocked."""
    stage_res = await stage_leave_request(
        employee_id="EMP-001",
        leave_type="Sick",
        start_date="2026-12-01",
        end_date="2026-12-31"  # 31 days exceeds available 6.0 days
    )
    token = stage_res["confirmation_token"]

    submit_res = await submit_leave_request(
        leave_type="Sick",
        start_date="2026-12-01",
        end_date="2026-12-31",
        confirmation_token=token
    )
    assert "error" in submit_res
    assert submit_res["error"] == "INSUFFICIENT_BALANCE"


# =====================================================================
# 3. Interactive Agent End-to-End Dialogue
# =====================================================================

@pytest.mark.asyncio
async def test_orchestrator_interactive_chat():
    """Test full multi-turn conversational interaction with WorkAgent."""
    res = await orchestrator.process_user_message(
        user_id="test-user-1",
        message_text="What is my current sick leave balance in WorkWeek?",
        current_employee_id="EMP-001"
    )
    assert res["reply"] != ""
    assert any(tc["name"] == "get_leave_balances" for tc in res["tool_calls"])
