"""Tests for Stateful Saga Orchestration and Compensation."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.saga.saga_manager import saga_manager


class TestSagaOrchestrator(unittest.TestCase):

    def test_saga_step_execution_and_compensation(self):
        """Tests multi-step transaction staging and automated compensation on failure."""
        steps = [
            {"step_name": "book_leave", "system": "workweek"},
            {"step_name": "create_continuity_ticket", "system": "serviceimmediately"},
        ]
        saga_id = saga_manager.create_saga("EMP-SG-1001", "LEAVE_AND_TICKET", steps)
        self.assertTrue(saga_id.startswith("saga_"))

        # Execute step 0 successfully
        res1 = saga_manager.execute_step(
            saga_id=saga_id,
            step_index=0,
            step_result={"receipt": {"system": "workweek", "operation": "submit_leave_request", "reference": "LR-2026-1001", "leave_type": "Vacation", "days_deducted": 2.0}},
            is_success=True,
        )
        self.assertEqual(res1["status"], "DRAFT")

        # Step 1 fails -> triggers compensation for Step 0
        res2 = saga_manager.execute_step(
            saga_id=saga_id,
            step_index=1,
            step_result={"error": "ServiceImmediately unavailable"},
            is_success=False,
        )
        self.assertEqual(res2["status"], "COMPENSATED")
        self.assertTrue(res2["resumable_draft_available"])


if __name__ == "__main__":
    unittest.main()
