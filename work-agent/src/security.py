"""
Security and Gating Module for WorkAgent (WorkWeek HCM).
Implements SDD Section 4.2: Confirm-Before-Commit Protocol, Cryptographic Payload Binding,
and Server-Side Subject Isolation (ADR-005).
"""

import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional, Tuple


def canonical_json(data: Any) -> str:
    """Serializes a dictionary or value into deterministic canonical JSON."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Computes SHA-256 hash of canonical JSON representation of the payload."""
    canonical_str = canonical_json(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class ConfirmationTokenManager:
    """Manages single-use, cryptographically bound confirmation tokens."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl_seconds = default_ttl_seconds
        # In-memory store: token -> {employee_id, action, payload_hash, payload, created_at, expires_at, consumed}
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def mint_token(
        self,
        employee_id: str,
        action: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Mints a single-use confirmation token bound to the exact payload SHA-256 hash.

        Returns a dictionary containing the token, payload_hash, expires_at, and review card data.
        """
        ttl = ttl_seconds or self.default_ttl_seconds
        now = time.time()
        payload_hash = compute_payload_hash(payload)
        token = f"CONFIRM-{uuid.uuid4().hex[:12].upper()}"

        record = {
            "token": token,
            "employee_id": employee_id,
            "action": action,
            "payload_hash": payload_hash,
            "payload": payload,
            "created_at": now,
            "expires_at": now + ttl,
            "consumed": False,
        }
        self._tokens[token] = record

        return {
            "token": token,
            "action": action,
            "employee_id": employee_id,
            "payload": payload,
            "payload_hash": payload_hash,
            "expires_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record["expires_at"])
            ),
            "ttl_seconds": ttl,
        }

    def verify_and_consume(
        self, token: str, inbound_payload: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Verifies that the token exists, is unexpired, unconsumed, and matches the inbound payload SHA-256 hash.

        If valid, marks the token as consumed and returns (True, \x27OK\x27, record).
        Otherwise returns (False, error_reason, None).
        """
        record = self._tokens.get(token)
        if not record:
            return False, "404_TOKEN_NOT_FOUND: Confirmation token is invalid or does not exist.", None

        if record["consumed"]:
            return False, "409_TOKEN_ALREADY_USED: Confirmation token has already been consumed (single-use enforced).", None

        now = time.time()
        if now > record["expires_at"]:
            return False, f"410_TOKEN_EXPIRED: Confirmation token expired at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(record['expires_at']))}.", None

        inbound_hash = compute_payload_hash(inbound_payload)
        if inbound_hash != record["payload_hash"]:
            return (
                False,
                f"409_PAYLOAD_TAMPERED: Inbound payload hash ({inbound_hash[:12]}...) does not match mint hash ({record['payload_hash'][:12]}...). Action aborted.",
                None,
            )

        # Mark as consumed
        record["consumed"] = True
        record["consumed_at"] = now
        return True, "CONFIRMATION_VALIDATED", record


# Global singleton instance
confirmation_manager = ConfirmationTokenManager()
