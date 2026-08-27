"""Tests for WorkWeek HCM Agent & MCP Tools with Strict Access Control."""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from src.agents.workweek_hcm_agent.agent import WorkWeekHCMAgent
from src.agents.workweek_hcm_agent.prompts import (
    DEFAULT_EMPLOYEE_ID,
    get_system_instruction,
)
from src.agents.workweek_hcm_agent.tools import (
    ACCESS_DENIED_MESSAGE,
    call_workweek_mcp,
    cancel_leave_request,
    enforce_subject_isolation,
    get_current_employee_id,
    get_employee_balances,
    get_leave_requests,
    get_personal_info,
    request_time_off,
    update_personal_info,
)


class TestWorkWeekHCMAgent(unittest.TestCase):
    """Unit and integration tests for WorkWeek HCM Agent and tools."""

    def test_system_prompt_generation(self):
        """Test system instruction formatting and subject isolation constraints."""
        instruction = get_system_instruction("EMP-545")
        self.assertIn("EMP-545", instruction)
        self.assertIn("STRICT ACCESS CONTROL", instruction)
        self.assertIn("ZERO-TRUST SUBJECT ISOLATION", instruction)
        self.assertIn("Access Denied (Subject Isolation Policy)", instruction)
        self.assertIn("get_employee_balances", instruction)

    def test_agent_initialization(self):
        """Test agent initialization with custom and default parameters."""
        agent = WorkWeekHCMAgent(employee_id="EMP-545")
        self.assertEqual(agent.name, "WorkWeek HCM Agent")
        self.assertEqual(agent.employee_id, "EMP-545")
        self.assertIn("work-week/mcp", agent.mcp_url)

    def test_subject_isolation_utility(self):
        """Test the deterministic enforce_subject_isolation helper."""
        # Same employee ID -> allowed (returns None)
        self.assertIsNone(enforce_subject_isolation("EMP-545", "EMP-545"))
        self.assertIsNone(enforce_subject_isolation("emp-545", "EMP-545"))

        # Different employee ID -> blocked (returns error string)
        res = enforce_subject_isolation("EMP-999", "EMP-545")
        self.assertIsNotNone(res)
        self.assertIn("Access Denied (Subject Isolation Policy)", res)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_tool_level_balances_cross_user_rejection(self, mock_call):
        """Test that get_employee_balances rejects cross-user queries deterministically."""
        res = asyncio.run(
            get_employee_balances(
                employee_id="EMP-999",
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_tool_level_personal_info_cross_user_rejection(self, mock_call):
        """Test that get_personal_info rejects cross-user queries deterministically."""
        res = asyncio.run(
            get_personal_info(
                employee_id="EMP-999",
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_tool_level_time_off_cross_user_rejection(self, mock_call):
        """Test that request_time_off rejects unauthorized bookings for another employee."""
        res = asyncio.run(
            request_time_off(
                employee_id="EMP-999",
                start_date="2026-09-01",
                end_date="2026-09-02",
                leave_type="Sick",
                days=2.0,
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_tool_level_cancel_cross_user_rejection(self, mock_call):
        """Test that cancel_leave_request rejects cross-user cancellations."""
        res = asyncio.run(
            cancel_leave_request(
                employee_id="EMP-999",
                request_id=1234,
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_authorized_get_employee_balances(self, mock_call):
        """Test get_employee_balances for the authenticated employee."""
        mock_call.return_value = "Employee EMP-545 Leave Balances:\n- Vacation: 15.0 days remaining\n- Sick: 10.0 days remaining"
        res = asyncio.run(get_employee_balances("EMP-545", authenticated_employee_id="EMP-545"))
        self.assertIn("Vacation: 15.0 days remaining", res)
        mock_call.assert_called_once()

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_authorized_get_personal_info(self, mock_call):
        """Test get_personal_info for the authenticated employee."""
        mock_call.return_value = "Employee EMP-545 Personal Info:\n- Address: Singapore Office\n- Phone: +65-6521-0000"
        res = asyncio.run(get_personal_info("EMP-545", authenticated_employee_id="EMP-545"))
        self.assertIn("Singapore Office", res)
        mock_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
