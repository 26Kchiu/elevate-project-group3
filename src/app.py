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

DEFAULT_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "elevate-taiwan-cohort-2")
DEFAULT_MODEL_NAME = os.getenv("MODEL_NAME", "auto")
DEFAULT_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
DEFAULT_MCP_TOKEN = os.getenv("DEFAULT_MCP_TOKEN", "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg")

# Avoid blocking gcloud call during WorkWeekHCMAgent._init_genai_client
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "vertex-auth-mode")

import google.auth
from google import genai
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import both specialist agents (without modifying workweek_hcm_agent codebase)
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
    description="Unified Portal for WorkWeek HCM Agent & ServiceImmediately ITSM Agent",
    version="2.0.0",
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

CANDIDATE_MODELS = [
    "gemini-3.7-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]

_hcm_agent = None
_itsm_agent = None


def extract_nested_exception(e: BaseException) -> str:
    """Recursively unwrap ExceptionGroup or TaskGroup errors to get the root error."""
    if hasattr(e, "exceptions") and e.exceptions:
        return " | ".join(extract_nested_exception(sub) for sub in e.exceptions)
    return str(e)


def get_shared_genai_client() -> genai.Client:
    """Create a non-blocking GenAI client using ADC credentials directly."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION)

    user_api_key = os.environ.get("GEMINI_API_KEY")
    if user_api_key and not user_api_key.startswith("vertex-"):
        return genai.Client(api_key=user_api_key)

    try:
        creds, _ = google.auth.default()
        return genai.Client(vertexai=True, project=project_id, location=location, credentials=creds)
    except Exception:
        return genai.Client(vertexai=True, project=project_id, location=location)


def get_hcm_agent(model_name: str = "auto") -> WorkWeekHCMAgent:
    global _hcm_agent
    if _hcm_agent is None or (model_name != "auto" and _hcm_agent.model_name != model_name):
        actual_model = "gemini-2.5-flash" if model_name == "auto" else model_name
        _hcm_agent = WorkWeekHCMAgent(model_name=actual_model)
        _hcm_agent.genai_client = get_shared_genai_client()
    return _hcm_agent


def get_itsm_agent(model_name: str = "auto") -> ServiceImmediatelyAgent:
    global _itsm_agent
    if _itsm_agent is None or _itsm_agent.model_name != model_name:
        _itsm_agent = ServiceImmediatelyAgent(model_name=model_name)
        _itsm_agent.genai_client = get_shared_genai_client()
    return _itsm_agent


class ChatRequest(BaseModel):
    message: str
    agent_target: Optional[str] = "auto"  # "workweek", "service_immediately", or "auto"
    model: Optional[str] = "auto"         # "auto", "gemini-3.7-flash", "gemini-2.5-flash", etc.
    employee_id: Optional[str] = None
    mcp_token: Optional[str] = None


def auto_route_query(query: str) -> str:
    """Intelligently route query to the right specialist agent based on intent keywords."""
    q_lower = query.lower()
    itsm_keywords = [
        "ticket", "incident", "it support", "laptop", "hardware", "software",
        "vpn", "network", "access", "iam", "password", "screen", "monitor",
        "keyboard", "service desk", "inc00", "repair", "itil", "crash", "bug",
        "工單", "報修", "電腦", "硬體", "軟體", "螢幕", "鍵盤", "網路", "密碼", "it支援"
    ]
    for kw in itsm_keywords:
        if kw in q_lower:
            return "service_immediately"
    return "workweek"


def enrich_prompt_with_language_alignment(prompt: str) -> str:
    """Ensure agent instructions enforce language alignment to the user's input."""
    instruction_note = (
        "\n[Instruction: Detect user's language and reply in the EXACT SAME language. "
        "If Chinese (繁體中文/簡體中文), reply completely in Chinese. If English, reply in English. "
        "Keep IDs and numbers precise.]"
    )
    return prompt + instruction_note


@app.get("/")
async def serve_index():
    """Serve the unified Web GUI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Static index.html not found.")
    return FileResponse(str(index_file))


@app.get("/api/status")
async def get_system_status(x_mcp_token: Optional[str] = Header(None)):
    """Check connectivity and session info for both WorkWeek and ServiceImmediately MCP servers."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    model = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
    project = os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)
    return {
        "status": "HEALTHY",
        "authenticated_employee_id": "EMP-545",
        "project_id": project,
        "default_model": model,
        "supported_models": CANDIDATE_MODELS,
        "agents": {
            "workweek_hcm": {
                "name": "WorkWeek HCM Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/",
                "model": "Auto-Selected Gemini",
                "project": project,
                "status": "ONLINE",
            },
            "service_immediately": {
                "name": "ServiceImmediately Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/",
                "model": "Auto-Selected Gemini",
                "project": project,
                "status": "ONLINE",
            },
        },
    }


@app.get("/api/hcm/profile")
async def get_hcm_profile(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek personal contact info."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        raw_output = await hcm_get_profile(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "raw_output": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hcm/balances")
async def get_hcm_balances(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek leave balances."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        raw_output = await hcm_get_balances(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "balances_text": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itsm/tickets")
async def get_itsm_tickets(x_mcp_token: Optional[str] = Header(None)):
    """Fetch ServiceImmediately incident tickets."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        raw_output = await itsm_list_tickets(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "tickets_raw": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_interaction(req: ChatRequest, x_mcp_token: Optional[str] = Header(None)):
    """Interactive multi-agent chat endpoint with auto-routing and auto-model selection."""
    token = req.mcp_token or x_mcp_token or DEFAULT_MCP_TOKEN
    target = req.agent_target or "auto"
    model_choice = req.model or "auto"

    if target == "auto":
        target = auto_route_query(req.message)

    enriched_prompt = enrich_prompt_with_language_alignment(req.message)

    try:
        if target == "service_immediately":
            agent = get_itsm_agent(model_name=model_choice)
            result = await agent.run(
                user_prompt=enriched_prompt,
                employee_id=req.employee_id or "EMP-545",
                mcp_token=token,
            )
        else:
            # For HCM, try candidate models if in auto mode
            models_to_try = CANDIDATE_MODELS if model_choice == "auto" else [model_choice] + [m for m in CANDIDATE_MODELS if m != model_choice]
            result = None
            last_err = None
            for m in models_to_try:
                try:
                    agent = get_hcm_agent(model_name=m)
                    result = await agent.run(
                        user_prompt=enriched_prompt,
                        employee_id=req.employee_id or "EMP-545",
                        mcp_token=token,
                    )
                    result["model"] = m
                    break
                except Exception as hcm_err:
                    last_err = hcm_err
                    continue
            if result is None and last_err:
                raise last_err

        return result
    except BaseException as e:
        err_msg = extract_nested_exception(e)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {err_msg}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Elevate HR & ITSM Multi-Agent Portal at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
