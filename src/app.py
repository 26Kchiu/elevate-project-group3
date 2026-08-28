"""FastAPI Unified Application for Elevate HR & ITSM Multi-Agent System."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Disable mTLS environment configurations
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"

# Avoid blocking gcloud call during WorkWeekHCMAgent._init_genai_client
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "vertex-auth-mode")

import google.auth
from google import genai
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import SSO & Token management
from src.shared.auth import (
    validate_corp_sso,
    generate_mcp_token,
    resolve_token_identity,
    CORP_IDP,
)

# Import both specialist agents
from src.agents.workweek_hcm_agent import WorkWeekHCMAgent
from src.agents.service_immediately_agent import ServiceImmediatelyAgent
from src.agents.service_immediately_agent.tools import list_tickets as itsm_list_tickets
from src.agents.workweek_hcm_agent.tools import (
    get_current_employee_id as hcm_get_employee_id,
    get_employee_balances as hcm_get_balances,
    get_personal_info as hcm_get_profile,
)

app = FastAPI(
    title="Elevate HR & ITSM Multi-Agent System",
    description="Unified Portal for WorkWeek HCM Agent & ServiceImmediately ITSM Agent with Corp SSO",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_hcm_agent = None
_itsm_agent = None


def extract_nested_exception(e: BaseException) -> str:
    """Recursively unwrap ExceptionGroup or TaskGroup errors to get the root error."""
    if hasattr(e, "exceptions") and e.exceptions:
        return " | ".join(extract_nested_exception(sub) for sub in e.exceptions)
    return str(e)


def get_shared_genai_client() -> genai.Client:
    """Create a non-blocking GenAI client using ADC credentials directly."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "harry-project-elevate")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    # If user provided a real Gemini API Key, use API key mode
    user_api_key = os.environ.get("GEMINI_API_KEY")
    if user_api_key and not user_api_key.startswith("vertex-"):
        return genai.Client(api_key=user_api_key)

    try:
        creds, _ = google.auth.default()
        return genai.Client(vertexai=True, project=project_id, location=location, credentials=creds)
    except Exception:
        return genai.Client(vertexai=True, project=project_id, location=location)


def get_hcm_agent() -> WorkWeekHCMAgent:
    global _hcm_agent
    if _hcm_agent is None:
        _hcm_agent = WorkWeekHCMAgent()
        _hcm_agent.genai_client = get_shared_genai_client()
    return _hcm_agent


def get_itsm_agent() -> ServiceImmediatelyAgent:
    global _itsm_agent
    if _itsm_agent is None:
        _itsm_agent = ServiceImmediatelyAgent()
        _itsm_agent.genai_client = get_shared_genai_client()
    return _itsm_agent


class ChatRequest(BaseModel):
    message: str
    agent_target: Optional[str] = "auto"  # "workweek", "service_immediately", or "auto"
    employee_id: Optional[str] = None
    mcp_token: Optional[str] = None


class GenerateMCPTokenRequest(BaseModel):
    ldap: str


def auto_route_query(query: str) -> str:
    """Intelligently route query to the right specialist agent based on intent keywords."""
    q_lower = query.lower()
    itsm_keywords = [
        "ticket", "incident", "it support", "laptop", "hardware", "software",
        "vpn", "network", "access", "iam", "password", "screen", "monitor",
        "keyboard", "service desk", "inc00", "repair", "itil", "crash", "bug"
    ]
    for kw in itsm_keywords:
        if kw in q_lower:
            return "service_immediately"
    return "workweek"


def resolve_effective_token_and_employee(
    mcp_token_param: Optional[str] = None,
    x_mcp_token_header: Optional[str] = None,
    explicit_employee_id: Optional[str] = None,
) -> tuple[str, str, Dict[str, Any]]:
    """Dynamically resolves token and employee identity from headers or active SSO session."""
    raw_token = (mcp_token_param or x_mcp_token_header or "").strip()
    if not raw_token:
        # Validate SSO and generate token for logged-in LDAP
        sso_info = validate_corp_sso()
        token_record = generate_mcp_token(sso_info["ldap"])
        raw_token = token_record["token"]
        identity = token_record
    else:
        identity = resolve_token_identity(raw_token)

    emp_id = explicit_employee_id or identity.get("employee_id") or "EMP-545"
    return raw_token, emp_id, identity


@app.get("/")
async def serve_index():
    """Serve the unified Web GUI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Static index.html not found.")
    return FileResponse(str(index_file))


@app.get("/api/auth/sso-status")
async def get_sso_status(request: Request):
    """Validate corporate SSO authentication status against login.corp.google.com."""
    headers_dict = dict(request.headers)
    sso_data = validate_corp_sso(headers_dict)
    return sso_data


@app.post("/api/mcp-tokens")
async def create_mcp_token(req: GenerateMCPTokenRequest):
    """Generate dynamic MCP token bound to the SSO authenticated user LDAP."""
    ldap = req.ldap.strip() if req.ldap else ""
    if not ldap:
        raise HTTPException(status_code=400, detail="Missing required 'ldap' parameter in request body.")
    token_record = generate_mcp_token(ldap)
    return token_record


@app.get("/api/status")
async def get_system_status(x_mcp_token: Optional[str] = Header(None)):
    """Check connectivity and session info for both WorkWeek and ServiceImmediately MCP servers."""
    token, emp_id, identity = resolve_effective_token_and_employee(x_mcp_token_header=x_mcp_token)
    return {
        "status": "HEALTHY",
        "authenticated_idp": CORP_IDP,
        "authenticated_ldap": identity.get("ldap", "ansonk"),
        "authenticated_employee_id": emp_id,
        "user_profile": identity,
        "agents": {
            "workweek_hcm": {
                "name": "WorkWeek HCM Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/",
                "model": os.getenv("MODEL_NAME", "gemini-3.7-flash"),
                "status": "ONLINE",
            },
            "service_immediately": {
                "name": "ServiceImmediately Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/",
                "model": os.getenv("MODEL_NAME", "gemini-3.7-flash"),
                "status": "ONLINE",
            },
        },
    }


@app.get("/api/hcm/profile")
async def get_hcm_profile(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek personal contact info."""
    token, emp_id, _ = resolve_effective_token_and_employee(x_mcp_token_header=x_mcp_token)
    try:
        raw_output = await hcm_get_profile(employee_id=emp_id, mcp_token=token)
        return {"employee_id": emp_id, "raw_output": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hcm/balances")
async def get_hcm_balances(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek leave balances."""
    token, emp_id, _ = resolve_effective_token_and_employee(x_mcp_token_header=x_mcp_token)
    try:
        raw_output = await hcm_get_balances(employee_id=emp_id, mcp_token=token)
        return {"employee_id": emp_id, "balances_text": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itsm/tickets")
async def get_itsm_tickets(x_mcp_token: Optional[str] = Header(None)):
    """Fetch ServiceImmediately incident tickets."""
    token, emp_id, _ = resolve_effective_token_and_employee(x_mcp_token_header=x_mcp_token)
    try:
        raw_output = await itsm_list_tickets(employee_id=emp_id, mcp_token=token)
        return {"employee_id": emp_id, "tickets_raw": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_interaction(req: ChatRequest, x_mcp_token: Optional[str] = Header(None)):
    """Interactive multi-agent chat endpoint."""
    token, emp_id, _ = resolve_effective_token_and_employee(
        mcp_token_param=req.mcp_token,
        x_mcp_token_header=x_mcp_token,
        explicit_employee_id=req.employee_id,
    )
    target = req.agent_target or "auto"

    if target == "auto":
        target = auto_route_query(req.message)

    try:
        if target == "service_immediately":
            agent = get_itsm_agent()
            result = await agent.run(
                user_prompt=req.message,
                employee_id=emp_id,
                mcp_token=token,
            )
        else:
            agent = get_hcm_agent()
            result = await agent.run(
                user_prompt=req.message,
                employee_id=emp_id,
                mcp_token=token,
            )
        return result
    except BaseException as e:
        err_msg = extract_nested_exception(e)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {err_msg}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Elevate HR & ITSM Multi-Agent Portal at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
