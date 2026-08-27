"""Tests for Cryptographic Confirmation Gate & Token Binding."""

import unittest
from enterprise.hr.agentic.hr_policy_agent.security.confirmation_gate import confirmation_gate


class TestConfirmationGate(unittest.TestCase):

    def test_mint_and_verify_token(self):
        """Tests minting and successfully consuming a confirmation token."""
        payload = {"action": "update_address", "address": "123 Main St"}
        token_id, card = confirmation_gate.mint_confirmation_token("saga_1", 1, payload)

        self.assertTrue(token_id.startswith("tok_"))
        self.assertEqual(len(card["payload_hash"]), 64)

        # Verify with identical payload
        valid, status = confirmation_gate.verify_and_consume_token(token_id, payload)
        self.assertTrue(valid)
        self.assertEqual(status, "VERIFIED")

    def test_tampered_payload_rejection(self):
        """Tests that modifying payload bytes triggers 409 hash mismatch."""
        staged_payload = {"action": "book_leave", "days": 2}
        token_id, _ = confirmation_gate.mint_confirmation_token("saga_2", 1, staged_payload)

        tampered_payload = {"action": "book_leave", "days": 10}  # Altered!
        valid, status = confirmation_gate.verify_and_consume_token(token_id, tampered_payload)
        self.assertFalse(valid)
        self.assertEqual(status, "PAYLOAD_HASH_MISMATCH_TAMPERED")

    def test_single_use_token_replay_rejection(self):
        """Tests that reusing an already consumed token fails."""
        payload = {"action": "test"}
        token_id, _ = confirmation_gate.mint_confirmation_token("saga_3", 1, payload)

        # First consumption
        valid1, _ = confirmation_gate.verify_and_consume_token(token_id, payload)
        self.assertTrue(valid1)

        # Second consumption (replay attack)
        valid2, status2 = confirmation_gate.verify_and_consume_token(token_id, payload)
        self.assertFalse(valid2)
        self.assertEqual(status2, "TOKEN_ALREADY_USED")


if __name__ == "__main__":
    unittest.main()
