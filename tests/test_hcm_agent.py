"""Tests for WorkWeek HCM Agent & Tools."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.agents.hcm_agent import hcm_agent
from enterprise.hr.agentic.hr_policy_agent.security.confirmation_gate import confirmation_gate


class TestHcmAgent(unittest.TestCase):

    def test_get_leave_balances(self):
        """Tests retrieving live leave balances for verified employee."""
        res = hcm_agent.get_balances("EMP-SG-1001")
        bal = res.get("balances", {})
        self.assertEqual(bal.get("vacation_days_accrued"), 20.0)
        self.assertEqual(bal.get("sick_leave_days_total"), 14.0)

    def test_leave_submission_requires_confirmation(self):
        """Tests that leave submissions require a confirmation token first."""
        res = hcm_agent.submit_leave(
            employee_id="EMP-SG-1001",
            leave_type="Vacation",
            start_date="2026-09-01",
            end_date="2026-09-02",
        )
        self.assertTrue(res.get("requires_confirmation"))
        self.assertIn("token", res)
        self.assertIn("confirmation_card", res)

    def test_leave_submission_with_valid_token(self):
        """Tests successful commit when valid confirmation token is provided."""
        payload = {
            "action_type": "submit_leave_request",
            "employee_id": "EMP-SG-1001",
            "leave_type": "Vacation",
            "start_date": "2026-10-01",
            "end_date": "2026-10-01",
            "half_day": False,
            "note": None,
        }
        token_id, _ = confirmation_gate.mint_confirmation_token(
            saga_id="saga_test_01", step_id=1, payload=payload
        )

        res = hcm_agent.submit_leave(
            employee_id="EMP-SG-1001",
            leave_type="Vacation",
            start_date="2026-10-01",
            end_date="2026-10-01",
            confirmation_token=token_id,
        )
        self.assertIn("receipt", res)
        self.assertEqual(res["receipt"]["leave_type"], "Vacation")
        self.assertTrue(res["receipt"]["reference"].startswith("LR-2026-"))


if __name__ == "__main__":
    unittest.main()
