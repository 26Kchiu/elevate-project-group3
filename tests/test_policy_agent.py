"""Tests for Grounded Policy Reasoning Agent using BigQuery Conversational Analytics."""

import unittest
from src.agents.policy_agent.agent import policy_agent


class TestPolicyAgentBQCA(unittest.TestCase):

    def test_bqca_outpatient_sick_leave_response(self):
        """Verify that the Policy Agent queries BigQuery Conversational Analytics and returns the policy answer."""
        res = policy_agent.process_policy_query("What is the outpatient sick leave allowance?")

        # Verify successful execution and correct policy entitlement
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("14 days", res["text"])

        # Verify provenance is from BigQuery Conversational API
        provenance = res.get("provenance") or {}
        self.assertEqual(provenance.get("engine"), "BigQuery Conversational API")
        self.assertIn("agent_98c36166-3d31-471e-8fce-4dc446069ad7", provenance.get("data_agent_id", ""))
        self.assertTrue(len(provenance.get("sql_queries", [])) > 0)

        # Verify source Cloud Storage hyperlink and page anchor
        self.assertIn("📄 **Source Document:**", res["text"])
        self.assertIn("https://storage.cloud.google.com/hr-km-landing-nonprod-elevate-taiwan-cohort-2/incoming/handbook.pdf#page=1", res["text"])
        self.assertEqual(provenance.get("pages"), [1])


if __name__ == "__main__":
    unittest.main()
