"""Tests for Supervisor / Root Orchestrator Agent."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.agents.supervisor_agent import supervisor_agent


class TestSupervisorAgent(unittest.TestCase):

    def test_intent_routing_to_balance_lookup(self):
        """Tests routing leave balance query to HCM agent."""
        res = supervisor_agent.handle_message(
            session_id="test-session-01",
            user_message="Check my leave balances",
            principal_email="kathleenchiu@google.com",
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["statement_class"], "system_of_record")
        self.assertIn("Vacation Leave", res["message"])

    def test_intent_routing_to_policy_agent(self):
        """Tests routing policy query to Policy Agent with GQL grounding."""
        res = supervisor_agent.handle_message(
            session_id="test-session-02",
            user_message="What is the travel meal daily reimbursement limit?",
            principal_email="kathleenchiu@google.com",
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("US $120", res["message"])
        self.assertTrue(len(res["citations"]) > 0)

    def test_supervisor_holds_zero_domain_tools_invariant(self):
        """Verifies structural invariant: Supervisor holds zero domain tools directly."""
        self.assertFalse(hasattr(supervisor_agent, "submit_leave_request"))
        self.assertFalse(hasattr(supervisor_agent, "create_incident"))


if __name__ == "__main__":
    unittest.main()
