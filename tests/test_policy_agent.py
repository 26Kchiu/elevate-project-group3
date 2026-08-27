"""Tests for Grounded Policy Reasoning Agent."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.agents.policy_agent import policy_agent


class TestPolicyAgent(unittest.TestCase):

    def test_direct_policy_qa(self):
        """Tests Class 1 Direct Policy Q&A with citable verbatim rule."""
        res = policy_agent.process_policy_query("What is the outpatient sick leave allowance?")
        self.assertEqual(res["response_class"], "direct")
        self.assertTrue(len(res["citations"]) > 0)
        self.assertIn("14 days", res["text"])
        self.assertIn("cl. 1.1", res["citations"][0])

    def test_composed_eligibility_qa(self):
        """Tests Class 2 Composed Multi-Clause Eligibility Q&A."""
        res = policy_agent.process_policy_query(
            "Am I eligible for bereavement leave for my grandmother?",
            employee_attributes={"relationship": "grandparent"}
        )
        self.assertEqual(res["response_class"], "composed")
        self.assertTrue(len(res["citations"]) >= 1)
        self.assertIn("4 weeks", res["text"])
        self.assertIn("close_loved_one", res["text"])

    def test_ungrounded_policy_refusal(self):
        """Tests Class 3 Ungrounded Policy Refusal when no bearing clause exists."""
        res = policy_agent.process_policy_query("What is the policy on employee cryptocurrency trading?")
        self.assertEqual(res["response_class"], "refuse")
        self.assertEqual(len(res["citations"]), 0)
        self.assertIn("could not find any governing", res["text"])

    def test_vacation_tier_lookup(self):
        """Tests vacation leave accrual rules."""
        res = policy_agent.process_policy_query("How many vacation days do I get with 4 years of service?")
        self.assertIn("20 days", res["text"])
        self.assertIn("cl. 1.2", res["citations"][0])


if __name__ == "__main__":
    unittest.main()
