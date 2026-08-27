"""Tests for ServiceImmediately ITSM Agent & MCP Tools with Strict Access Control."""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from src.agents.service_immediately_agent.agent import ServiceImmediatelyAgent
from src.agents.service_immediately_agent.prompts import (
    DEFAULT_EMPLOYEE_ID,
    get_system_instruction,
)
from src.agents.service_immediately_agent.tools import (
    ACCESS_DENIED_MESSAGE,
    add_ticket_comment,
    call_service_immediately_mcp,
    create_ticket,
    enforce_subject_isolation,
    format_tickets_output,
    list_tickets,
    update_ticket_status,
)


class TestItsmAgent(unittest.TestCase):
    """Unit and integration tests for ServiceImmediately Agent and tools."""

    def test_system_prompt_generation(self):
        """Test system instruction formatting and subject isolation constraints."""
        instruction = get_system_instruction("EMP-545")
        self.assertIn("EMP-545", instruction)
        self.assertIn("STRICT ACCESS CONTROL", instruction)
        self.assertIn("ZERO-TRUST SUBJECT ISOLATION", instruction)
        self.assertIn("Access Denied (Subject Isolation Policy)", instruction)
        self.assertIn("list_tickets", instruction)

    def test_agent_initialization(self):
        """Test agent initialization with custom and default parameters."""
        agent = ServiceImmediatelyAgent(employee_id="EMP-545")
        self.assertEqual(agent.name, "ServiceImmediately Agent")
        self.assertEqual(agent.employee_id, "EMP-545")
        self.assertIn("service-immediately/mcp", agent.mcp_url)

    def test_subject_isolation_utility(self):
        """Test the deterministic enforce_subject_isolation helper."""
        self.assertIsNone(enforce_subject_isolation("EMP-545", "EMP-545"))
        self.assertIsNone(enforce_subject_isolation("emp-545", "EMP-545"))

        res = enforce_subject_isolation("EMP-999", "EMP-545")
        self.assertIsNotNone(res)
        self.assertIn("Access Denied (Subject Isolation Policy)", res)

    @patch("src.agents.service_immediately_agent.tools.call_service_immediately_mcp")
    def test_tool_level_list_tickets_cross_user_rejection(self, mock_call):
        """Test that list_tickets rejects cross-user queries deterministically."""
        res = asyncio.run(
            list_tickets(
                employee_id="EMP-999",
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.service_immediately_agent.tools.call_service_immediately_mcp")
    def test_tool_level_create_ticket_cross_user_rejection(self, mock_call):
        """Test that create_ticket rejects creating tickets on behalf of other employees."""
        res = asyncio.run(
            create_ticket(
                requested_by="EMP-999",
                category="Hardware",
                short_description="Monitor flickering",
                authenticated_employee_id="EMP-545",
            )
        )
        self.assertEqual(res, ACCESS_DENIED_MESSAGE)
        mock_call.assert_not_called()

    @patch("src.agents.service_immediately_agent.tools.call_service_immediately_mcp")
    def test_authorized_list_tickets(self, mock_call):
        """Test listing tickets for the authenticated employee."""
        mock_call.return_value = '[{"ticket_id": "INC0003370", "short_description": "Onboarding setup"}]'
        res = asyncio.run(list_tickets("EMP-545", authenticated_employee_id="EMP-545"))
        self.assertIn("INC0003370", res)
        mock_call.assert_called_once()

    def test_format_tickets_output(self):
        """Test formatting JSON tickets into structured string."""
        sample_json = '[{"ticket_id": "INC123", "caller_name": "Harry Lin", "requested_by": "EMP-545", "category": "Hardware", "priority": "2 - High", "status": "In Progress", "assignment_group": "Service Desk", "assigned_to": "IT Support", "short_description": "Laptop battery issue", "created_at": "2026-08-27"}]'
        formatted = format_tickets_output(sample_json)
        self.assertIn("INC123", formatted)
        self.assertIn("Laptop battery issue", formatted)
        self.assertIn("2 - High", formatted)


if __name__ == "__main__":
    unittest.main()
