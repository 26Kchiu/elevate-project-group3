"""Tests for ServiceImmediately ITSM Agent & Tools."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.agents.itsm_agent import itsm_agent
from enterprise.hr.agentic.hr_policy_agent.security.confirmation_gate import confirmation_gate


class TestItsmAgent(unittest.TestCase):

    def test_list_my_tickets(self):
        """Tests listing tickets for acting employee."""
        res = itsm_agent.list_tickets("EMP-SG-1001")
        self.assertEqual(res.get("status_code"), 200)
        self.assertTrue(len(res.get("tickets", [])) >= 1)

    def test_create_incident_requires_confirmation(self):
        """Tests that incident creation triggers confirmation review card."""
        res = itsm_agent.create_incident(
            employee_id="EMP-SG-1001",
            short_description="Request for new laptop charger",
            category="Hardware",
        )
        self.assertTrue(res.get("requires_confirmation"))
        self.assertIn("token", res)

    def test_create_incident_with_token(self):
        """Tests successful incident creation with verified token."""
        payload = {
            "action_type": "create_incident",
            "employee_id": "EMP-SG-1001",
            "short_description": "Request for privacy screen filter",
            "category": "Facilities",
            "priority": "3 - Moderate",
            "details": None,
        }
        token_id, _ = confirmation_gate.mint_confirmation_token(
            saga_id="saga_test_itsm", step_id=1, payload=payload
        )

        res = itsm_agent.create_incident(
            employee_id="EMP-SG-1001",
            short_description="Request for privacy screen filter",
            category="Facilities",
            priority="3 - Moderate",
            confirmation_token=token_id,
        )
        self.assertIn("receipt", res)
        self.assertTrue(res["receipt"]["ticket_id"].startswith("INC-2026-"))


if __name__ == "__main__":
    unittest.main()
