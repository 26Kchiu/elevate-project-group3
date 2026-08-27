"""End-to-End Multi-Agent Conversational Integration Tests."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.agents.supervisor_agent import supervisor_agent


class TestEndToEndConversationalFlows(unittest.TestCase):

    def test_full_bereavement_policy_to_eligibility_flow(self):
        """Tests end-to-end multi-turn flow: policy lookup -> personal eligibility."""
        # Turn 1: General Policy Lookup
        turn1 = supervisor_agent.handle_message(
            session_id="e2e-session-100",
            user_message="What is the bereavement leave policy?",
            principal_email="kathleenchiu@google.com",
        )
        self.assertEqual(turn1["status"], "SUCCESS")
        self.assertIn("4 weeks", turn1["message"])
        self.assertIn("cl. 3.1", turn1["citations"][0])

        # Turn 2: Personal Grandmother Eligibility
        turn2 = supervisor_agent.handle_message(
            session_id="e2e-session-100",
            user_message="Am I eligible for bereavement leave for my grandmother?",
            principal_email="kathleenchiu@google.com",
        )
        self.assertEqual(turn2["status"], "SUCCESS")
        self.assertIn("4 weeks", turn2["message"])

    def test_full_leave_booking_confirmation_flow(self):
        """Tests leave application -> confirmation card -> execution commit."""
        # Turn 1: Initial request
        turn1 = supervisor_agent.handle_message(
            session_id="e2e-session-200",
            user_message="Book vacation leave from 2026-11-02 to 2026-11-04",
            principal_email="kathleenchiu@google.com",
        )
        self.assertEqual(turn1["status"], "CONFIRMATION_REQUIRED")
        token = turn1.get("token")
        self.assertIsNotNone(token)

        # Turn 2: User Confirms Execution
        turn2 = supervisor_agent.handle_message(
            session_id="e2e-session-200",
            user_message="Confirm and execute booking",
            principal_email="kathleenchiu@google.com",
            confirmation_token=token,
        )
        self.assertEqual(turn2["status"], "SUCCESS")
        self.assertIn("officially recorded in WorkWeek", turn2["message"])


if __name__ == "__main__":
    unittest.main()
