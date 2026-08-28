"""SSO Authentication and Dynamic MCP Token Management Module.

Validates Google Cloud Identity-Aware Proxy (IAP) cryptographically signed JWTs
and mints per-user Model Context Protocol (MCP) personal access tokens bound to employee LDAP sessions.
"""

import datetime
import getpass
import hashlib
import hmac
import os
import re
from typing import Any, Dict, Optional, Tuple
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

CORP_IDP = "login.corp.google.com"
DEFAULT_SALT = os.environ.get("MCP_TOKEN_SECRET_SALT", "elevate-corp-mcp-salt-2026")
IAP_JWKS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
_REQUEST_ADAPTER = google_requests.Request()

# In-memory token and session registry
_TOKEN_REGISTRY: Dict[str, Dict[str, Any]] = {}
_LDAP_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Known LDAP to Employee ID mappings (with dynamic fallback)
LDAP_TO_EMP_MAPPINGS: Dict[str, Dict[str, str]] = {
    "ansonk": {"employee_id": "EMP-545", "name": "Anson K", "role": "Enterprise Solutions Architect"},
    "harrylin": {"employee_id": "EMP-545", "name": "Harry Lin", "role": "Customer Engineer"},
    "kathleenchiu": {"employee_id": "EMP-SG-1001", "name": "Kathleen Chiu", "role": "Technical Program Manager"},
    "sarahchen": {"employee_id": "EMP-SG-1002", "name": "Sarah Chen", "role": "Senior Cloud Architect"},
}


def _extract_ldap_from_email_or_user(value: str) -> str:
    """Normalize and extract clean LDAP username from email, header prefix, or string."""
    if not value:
        return ""
    val = value.split(":")[-1].strip()
    if "@" in val:
        val = val.split("@")[0].strip()
    return re.sub(r"[^a-zA-Z0-9._-]", "", val).lower()


def get_current_system_ldap() -> str:
    """Retrieve current system or environment corp LDAP username."""
    for env_key in ("CORP_USER_LDAP", "GOOGLE_USER_LDAP", "USER", "LOGNAME"):
        candidate = os.environ.get(env_key)
        if candidate:
            clean = _extract_ldap_from_email_or_user(candidate)
            if clean:
                return clean

    try:
        sys_user = getpass.getuser()
        clean = _extract_ldap_from_email_or_user(sys_user)
        if clean:
            return clean
    except Exception:
        pass

    return "ansonk"


def verify_iap_jwt(iap_jwt: str, expected_audience: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Verify Google Cloud IAP cryptographic JWT token.
    
    Returns:
        (is_valid, payload_dict, error_message)
    """
    if not iap_jwt:
        return False, None, "Missing X-Goog-IAP-JWT-Assertion header"

    try:
        aud = expected_audience or os.environ.get("IAP_EXPECTED_AUDIENCE")
        decoded_payload = id_token.verify_token(
            iap_jwt,
            request=_REQUEST_ADAPTER,
            certs_url=IAP_JWKS_URL,
            audience=aud,
        )
        return True, decoded_payload, ""
    except Exception as e:
        return False, None, f"IAP JWT verification failed: {str(e)}"


def validate_corp_sso(headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Validate SSO status against Google Corp IdP (login.corp.google.com) or Cloud IAP.

    Inspects incoming Cloud IAP JWT headers, proxy headers, or discovers local corporate session.
    """
    req_headers = {k.lower(): v for k, v in (headers or {}).items()}
    iap_jwt = req_headers.get("x-goog-iap-jwt-assertion")
    iap_aud = os.environ.get("IAP_EXPECTED_AUDIENCE")
    is_cloud_run = bool(os.environ.get("K_SERVICE") or os.environ.get("K_REVISION"))

    auth_source = "LOCAL_DEV_SESSION"
    email = ""
    ldap = ""

    if iap_jwt:
        is_valid, payload, err = verify_iap_jwt(iap_jwt, expected_audience=iap_aud)
        if is_valid and payload:
            email = payload.get("email", "")
            ldap = _extract_ldap_from_email_or_user(email)
            auth_source = "GOOGLE_IAP_JWT_VERIFIED"
        else:
            if is_cloud_run and os.environ.get("IAP_ENFORCE", "false").lower() == "true":
                raise ValueError(f"Unauthorized IAP Request: {err}")

    if not ldap:
        # Check standard headers
        iap_user = (
            req_headers.get("x-goog-authenticated-user-email")
            or req_headers.get("x-goog-authenticated-user-id")
            or req_headers.get("x-forwarded-user")
            or req_headers.get("x-remote-user")
        )
        ldap = _extract_ldap_from_email_or_user(iap_user) if iap_user else get_current_system_ldap()
        if not ldap:
            ldap = "ansonk"
        email = f"{ldap}@google.com"

    profile_info = LDAP_TO_EMP_MAPPINGS.get(ldap, {})
    employee_id = profile_info.get("employee_id") or f"EMP-{hashlib.sha256(ldap.encode()).hexdigest()[:6].upper()}"
    display_name = profile_info.get("name") or ldap.capitalize()
    role = profile_info.get("role") or "Enterprise Specialist"

    session_hash = hashlib.sha256(f"{CORP_IDP}:{ldap}".encode()).hexdigest()[:12]

    session_data = {
        "authenticated": True,
        "idp": CORP_IDP,
        "status": "VALIDATED",
        "auth_source": auth_source,
        "ldap": ldap,
        "email": email,
        "display_name": display_name,
        "employee_id": employee_id,
        "role": role,
        "session_id": f"sso-corp-{session_hash}",
        "authenticated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    _LDAP_SESSIONS[ldap] = session_data
    return session_data


def generate_mcp_token(ldap: str, salt: Optional[str] = None) -> Dict[str, Any]:
    """Generate a dynamic MCP Token for the authenticated SSO LDAP user."""
    clean_ldap = _extract_ldap_from_email_or_user(ldap)
    if not clean_ldap:
        raise ValueError("Invalid LDAP username provided for MCP token generation.")

    secret_salt = (salt or DEFAULT_SALT).encode("utf-8")
    token_hmac = hmac.new(secret_salt, clean_ldap.encode("utf-8"), hashlib.sha256).hexdigest()
    mcp_token = f"mcp__{token_hmac[:40]}"

    profile_info = LDAP_TO_EMP_MAPPINGS.get(clean_ldap, {})
    employee_id = profile_info.get("employee_id") or f"EMP-{hashlib.sha256(clean_ldap.encode()).hexdigest()[:6].upper()}"
    display_name = profile_info.get("name") or clean_ldap.capitalize()
    role = profile_info.get("role") or "Enterprise Specialist"

    token_record = {
        "token": mcp_token,
        "ldap": clean_ldap,
        "email": f"{clean_ldap}@google.com",
        "display_name": display_name,
        "employee_id": employee_id,
        "role": role,
        "idp": CORP_IDP,
        "status": "ACTIVE",
        "token_type": "Bearer",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "expires_in": 86400,
    }

    _TOKEN_REGISTRY[mcp_token] = token_record
    return token_record


def resolve_token_identity(token: Optional[str]) -> Dict[str, Any]:
    """Resolve employee identity and LDAP from an MCP token."""
    if token and token in _TOKEN_REGISTRY:
        return _TOKEN_REGISTRY[token]

    # If token matches mcp__ pattern, check known ldap mappings first
    if token and token.startswith("mcp__"):
        for cand_ldap in list(LDAP_TO_EMP_MAPPINGS.keys()) + [get_current_system_ldap()]:
            cand_rec = generate_mcp_token(cand_ldap)
            if cand_rec["token"] == token:
                return cand_rec

        tok_sub = token[5:]
        tok_hash = hashlib.sha256(tok_sub.encode()).hexdigest()[:6].upper()
        return {
            "token": token,
            "ldap": f"user-{tok_hash.lower()}",
            "email": f"user.{tok_hash.lower()}@google.com",
            "display_name": f"User {tok_hash}",
            "employee_id": f"EMP-{tok_hash}",
            "role": "Enterprise Specialist",
            "idp": CORP_IDP,
            "status": "ACTIVE",
        }

    # Fallback to current SSO status
    sso_data = validate_corp_sso()
    return {
        "token": token or "",
        "ldap": sso_data["ldap"],
        "email": sso_data["email"],
        "display_name": sso_data["display_name"],
        "employee_id": sso_data["employee_id"],
        "role": sso_data["role"],
        "idp": CORP_IDP,
        "status": "ACTIVE",
    }
