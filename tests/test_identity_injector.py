"""Tests for Identity Injection & TC-SEC-02 Cross-User Isolation."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.security.identity_injector import identity_injector


class TestIdentityInjector(unittest.TestCase):

    def test_resolve_principal(self):
        """Tests mapping authenticated IAM principal to employee_id."""
        emp_id = identity_injector.resolve_principal_to_employee_id("kathleenchiu@google.com")
        self.assertEqual(emp_id, "EMP-SG-1001")

        sarah_id = identity_injector.resolve_principal_to_employee_id("sarah.chen@altostrat.com")
        self.assertEqual(sarah_id, "EMP-SG-1002")

    def test_sanitize_tool_parameters_strips_injected_ids(self):
        """Verifies TC-SEC-02 release gate: User/model supplied employee IDs are stripped."""
        malicious_params = {
            "employee_id": "EMP-SG-9999",  # Attacker attempt
            "target_employee_id": "EMP-SG-9999",
            "leave_type": "Vacation",
        }
        sanitized = identity_injector.sanitize_tool_parameters(
            malicious_params, verified_employee_id="EMP-SG-1001"
        )
        self.assertEqual(sanitized["employee_id"], "EMP-SG-1001")
        self.assertNotIn("target_employee_id", sanitized)


if __name__ == "__main__":
    unittest.main()
