"""Tests for Human Curation Gate & 15m Withdrawal SLA."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.knowledge.curation_gate import curation_gate


class TestCurationGate(unittest.TestCase):

    def test_confidence_band_classification(self):
        """Tests classification of extraction scores into Bands A-D."""
        self.assertEqual(curation_gate.classify_band(0.95), "Band A")
        self.assertEqual(curation_gate.classify_band(0.75), "Band B")
        self.assertEqual(curation_gate.classify_band(0.55), "Band C")
        self.assertEqual(curation_gate.classify_band(0.30), "Band D")

    def test_curation_approval_workflow(self):
        """Tests adding to queue and human approval transition."""
        node = {
            "node_id": "CLAUSE-TEST-01",
            "clause_ref": "9.1",
            "title": "Test Clause",
            "verbatim_text": "Sample policy statement for review.",
            "extraction_confidence": 0.72,  # Band B
        }
        curation_gate.add_to_review_queue(node)
        pending = curation_gate.list_pending()
        self.assertTrue(any(p["node_id"] == "CLAUSE-TEST-01" for p in pending))

        app_res = curation_gate.approve_assertion("CLAUSE-TEST-01", "curator@altostrat.com")
        self.assertEqual(app_res["status"], "SUCCESS")
        self.assertEqual(app_res["state"], "published")

    def test_instant_policy_withdrawal_sla(self):
        """Tests 15-minute policy withdrawal SLA enforcement."""
        w_res = curation_gate.withdraw_policy(
            doc_id="POL-SG-HANDBOOK-001",
            curator_ldap="curator@altostrat.com",
            reason="Superseded by v2.1 update",
        )
        self.assertEqual(w_res["status"], "WITHDRAWN")
        self.assertEqual(w_res["sla_guarantee"], "< 15 minutes")


if __name__ == "__main__":
    unittest.main()
