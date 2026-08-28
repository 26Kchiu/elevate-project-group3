"""Unit tests for SSO Validation (login.corp.google.com) and Dynamic MCP Token Generation."""

import unittest
from src.shared.auth import (
    validate_corp_sso,
    generate_mcp_token,
    resolve_token_identity,
    CORP_IDP,
    _extract_ldap_from_email_or_user,
)


class TestSSOAndMCPTokens(unittest.TestCase):

    def test_extract_ldap_from_email_or_user(self):
        """Test LDAP normalization from various header and email formats."""
        self.assertEqual(_extract_ldap_from_email_or_user("accounts.google.com:ansonk@google.com"), "ansonk")
        self.assertEqual(_extract_ldap_from_email_or_user("sarahchen@google.com"), "sarahchen")
        self.assertEqual(_extract_ldap_from_email_or_user("harrylin"), "harrylin")
        self.assertEqual(_extract_ldap_from_email_or_user(""), "")

    def test_validate_corp_sso_default(self):
        """Test default corporate SSO discovery."""
        sso_data = validate_corp_sso()
        self.assertTrue(sso_data["authenticated"])
        self.assertEqual(sso_data["idp"], CORP_IDP)
        self.assertEqual(sso_data["status"], "VALIDATED")
        self.assertTrue(bool(sso_data["ldap"]))
        self.assertTrue(sso_data["email"].endswith("@google.com"))
        self.assertTrue(sso_data["session_id"].startswith("sso-corp-"))

    def test_validate_corp_sso_with_iap_headers(self):
        """Test SSO validation with Cloud IAP / Corp proxy headers."""
        headers = {
            "X-Goog-Authenticated-User-Email": "accounts.google.com:sarahchen@google.com",
            "X-Goog-Authenticated-User-Id": "104928374",
        }
        sso_data = validate_corp_sso(headers)
        self.assertTrue(sso_data["authenticated"])
        self.assertEqual(sso_data["idp"], "login.corp.google.com")
        self.assertEqual(sso_data["ldap"], "sarahchen")
        self.assertEqual(sso_data["email"], "sarahchen@google.com")
        self.assertEqual(sso_data["employee_id"], "EMP-SG-1002")

    def test_generate_mcp_token(self):
        """Test dynamic generation of MCP tokens bound to LDAP."""
        token_record = generate_mcp_token("ansonk")
        self.assertIn("token", token_record)
        self.assertTrue(token_record["token"].startswith("mcp__"))
        self.assertEqual(token_record["ldap"], "ansonk")
        self.assertEqual(token_record["status"], "ACTIVE")
        self.assertEqual(token_record["idp"], CORP_IDP)
        self.assertEqual(token_record["employee_id"], "EMP-545")

        # Verify identity resolution
        identity = resolve_token_identity(token_record["token"])
        self.assertEqual(identity["ldap"], "ansonk")
        self.assertEqual(identity["employee_id"], "EMP-545")

    def test_generate_mcp_token_invalid_ldap(self):
        """Test error when empty LDAP is provided."""
        with self.assertRaises(ValueError):
            generate_mcp_token("")


if __name__ == "__main__":
    unittest.main()
