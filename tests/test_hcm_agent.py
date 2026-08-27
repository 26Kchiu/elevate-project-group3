"""Tests for WorkWeek HCM Agent & MCP Tools."""

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
    call_workweek_mcp,
    cancel_leave_request,
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
        self.assertIn("Subject Isolation", instruction)
        self.assertIn("https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/", instruction)
        self.assertIn("get_employee_balances", instruction)

    def test_agent_initialization(self):
        """Test agent initialization with custom and default parameters."""
        agent = WorkWeekHCMAgent(employee_id="EMP-545")
        self.assertEqual(agent.name, "WorkWeek HCM Agent")
        self.assertEqual(agent.employee_id, "EMP-545")
        self.assertIn("work-week/mcp", agent.mcp_url)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_get_current_employee_id_mock(self, mock_call):
        """Test get_current_employee_id tool invocation."""
        mock_call.return_value = "EMP-545"
        res = asyncio.run(get_current_employee_id())
        self.assertEqual(res, "EMP-545")
        mock_call.assert_called_once_with("get_current_employee_id", {}, unittest.mock.ANY, unittest.mock.ANY)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_get_employee_balances_mock(self, mock_call):
        """Test get_employee_balances tool invocation."""
        mock_call.return_value = "Employee EMP-545 Leave Balances:\n- Vacation: 15.0 days remaining\n- Sick: 10.0 days remaining"
        res = asyncio.run(get_employee_balances("EMP-545"))
        self.assertIn("Vacation: 15.0 days remaining", res)
        mock_call.assert_called_once_with("get_employee_balances", {"employee_id": "EMP-545"}, unittest.mock.ANY, unittest.mock.ANY)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_get_personal_info_mock(self, mock_call):
        """Test get_personal_info tool invocation."""
        mock_call.return_value = "Employee EMP-545 Personal Info:\n- Address: Singapore Office\n- Phone: +65-6521-0000"
        res = asyncio.run(get_personal_info("EMP-545"))
        self.assertIn("Singapore Office", res)
        mock_call.assert_called_once_with("get_personal_info", {"employee_id": "EMP-545"}, unittest.mock.ANY, unittest.mock.ANY)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_request_time_off_mock(self, mock_call):
        """Test request_time_off tool invocation."""
        mock_call.return_value = "Successfully submitted leave request 2039 for EMP-545"
        res = asyncio.run(
            request_time_off(
                employee_id="EMP-545",
                start_date="2026-09-01",
                end_date="2026-09-03",
                leave_type="Sick",
                days=3.0,
            )
        )
        self.assertIn("Successfully submitted", res)

    @patch("src.agents.workweek_hcm_agent.tools.call_workweek_mcp")
    def test_cancel_leave_request_mock(self, mock_call):
        """Test cancel_leave_request tool invocation."""
        mock_call.return_value = "Successfully cancelled leave request 2038"
        res = asyncio.run(cancel_leave_request(employee_id="EMP-545", request_id=2038))
        self.assertIn("Successfully cancelled", res)


if __name__ == "__main__":
    unittest.main()
