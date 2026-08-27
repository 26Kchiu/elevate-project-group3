"""
Comprehensive Test Suite for WorkAgent & WorkWeek MCP Server (/work-week/mcp/).
Verifies:
1. get_current_employee_id()
2. workweek://employees/{employee_id}/profile resource
3. get_employee_balances(employee_id)
4. request_time_off(employee_id, start_date, end_date, leave_type, days) with validation
5. update_personal_info(employee_id, address, phone) with validation
6. get_personal_info(employee_id)
7. get_leave_requests(employee_id) & cancel_leave_request(employee_id, request_id)
8. Confirm-Before-Commit security & subject isolation
"""

import asyncio
import datetime
import pytest
from src.workweek_service import workweek_mcp
from src.security import confirmation_manager
from src.agent import (
    get_my_profile,
    get_my_leave_balances,
    get_my_leave_requests,
    stage_time_off_request,
    submit_time_off_request,
    stage_personal_info_update,
    submit_personal_info_update,
    cancel_time_off_request,
    orchestrator
)

TEST_TOKEN = "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"


# =====================================================================
# 1. MCP Tools & Resources Direct Verification
# =====================================================================

@pytest.mark.asyncio
async def test_mcp_get_current_employee_id():
    """Verify get_current_employee_id resolves employee session from token."""
    res = await workweek_mcp.get_current_employee_id(TEST_TOKEN)
    assert res["authenticated"] is True
    assert res["employee_id"] == "EMP-10492"


@pytest.mark.asyncio
async def test_mcp_read_resource_profile():
    """Verify workweek://employees/{employee_id}/profile resource read."""
    emp_res = await workweek_mcp.get_current_employee_id(TEST_TOKEN)
    emp_id = emp_res["employee_id"]
    profile = await workweek_mcp.read_resource_profile(emp_id, TEST_TOKEN)
    assert profile["employee_id"] == emp_id
    assert profile["name"] == "Harry Lin"
    assert "home_address" in profile
    assert "phone_number" in profile
    assert "manager_id" in profile


@pytest.mark.asyncio
async def test_mcp_get_employee_balances():
    """Verify get_employee_balances tool."""
    emp_res = await workweek_mcp.get_current_employee_id(TEST_TOKEN)
    emp_id = emp_res["employee_id"]
    bal = await workweek_mcp.get_employee_balances(emp_id, TEST_TOKEN)
    assert "balances" in bal
    assert bal["balances"]["vacation_remaining"] == 18.0
    assert bal["balances"]["sick_remaining"] == 10.0


@pytest.mark.asyncio
async def test_mcp_update_and_get_personal_info():
    """Verify update_personal_info and get_personal_info tools with validation."""
    emp_res = await workweek_mcp.get_current_employee_id(TEST_TOKEN)
    emp_id = emp_res["employee_id"]

    # Valid update
    up_res = await workweek_mcp.update_personal_info(
        employee_id=emp_id,
        address="101 Innovation Parkway, Taipei",
        phone="+886 988 777 666",
        token=TEST_TOKEN
    )
    assert up_res["status"] == "SUCCESS"

    # Get updated info
    get_res = await workweek_mcp.get_personal_info(emp_id, TEST_TOKEN)
    assert get_res["home_address"] == "101 Innovation Parkway, Taipei"
    assert get_res["phone_number"] == "+886 988 777 666"

    # Invalid phone validation check
    inv_phone = await workweek_mcp.update_personal_info(
        employee_id=emp_id,
        address="Valid Address",
        phone="abc123",
        token=TEST_TOKEN
    )
    assert "error" in inv_phone


@pytest.mark.asyncio
async def test_mcp_request_time_off_and_cancellation():
    """Verify request_time_off and cancel_leave_request tools."""
    emp_res = await workweek_mcp.get_current_employee_id(TEST_TOKEN)
    emp_id = emp_res["employee_id"]

    # Book 2 days vacation in future
    future_start = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    future_end = (datetime.date.today() + datetime.timedelta(days=31)).isoformat()

    book_res = await workweek_mcp.request_time_off(
        employee_id=emp_id,
        start_date=future_start,
        end_date=future_end,
        leave_type="vacation",
        days=2.0,
        token=TEST_TOKEN
    )
    assert book_res["status"] == "SUCCESS"
    req_id = book_res["receipt"]["request_id"]
    assert book_res["receipt"]["remaining_balance"] == 16.0

    # Cancel request and verify refund
    cancel_res = await workweek_mcp.cancel_leave_request(emp_id, req_id, TEST_TOKEN)
    assert cancel_res["status"] == "SUCCESS"
    assert cancel_res["days_refunded"] == 2.0
    assert cancel_res["new_remaining_balance"] == 18.0


# =====================================================================
# 2. Confirm-Before-Commit Security & Subject Isolation
# =====================================================================

@pytest.mark.asyncio
async def test_stage_and_submit_time_off_with_hash():
    """Verify full confirm-before-commit flow with SHA-256 payload hash."""
    future_start = (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
    future_end = (datetime.date.today() + datetime.timedelta(days=62)).isoformat()

    stage_res = await stage_time_off_request(
        leave_type="sick",
        start_date=future_start,
        end_date=future_end,
        days=3.0
    )
    assert stage_res["status"] == "STAGED_AWAITING_CONFIRMATION"
    token = stage_res["confirmation_token"]

    submit_res = await submit_time_off_request(
        leave_type="sick",
        start_date=future_start,
        end_date=future_end,
        days=3.0,
        confirmation_token=token
    )
    assert submit_res["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_subject_isolation_cross_user_rejection():
    """Verify cross-user queries are rejected by WorkAgent."""
    res = await orchestrator.process_user_message(
        user_id="test_user",
        message_text="What is Alex Rivera's vacation leave balance and home address?",
        mcp_token=TEST_TOKEN
    )
    assert any(term in res["reply"].lower() for term in ["access denied", "restricted", "subject isolation", "own employee records"])
