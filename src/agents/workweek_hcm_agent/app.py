"""FastAPI Server & Web GUI Backend for WorkWeek HCM Agent."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.shared.auth import (
    validate_corp_sso,
    generate_mcp_token,
    resolve_token_identity,
    CORP_IDP,
)
from src.agents.workweek_hcm_agent.agent import WorkWeekHCMAgent
from src.agents.workweek_hcm_agent.tools import (
    DEFAULT_MCP_TOKEN,
    DEFAULT_MCP_URL,
    call_workweek_mcp,
    cancel_leave_request,
    get_current_employee_id,
    get_employee_balances,
    get_leave_requests,
    get_personal_info,
    request_time_off,
    update_personal_info,
)

app = FastAPI(
    title="WorkWeek HCM Agent — Virtual Assistant",
    description="Interactive Web GUI and REST API connecting to WorkWeek SaaS MCP Server (/work-week/mcp/)",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Singleton agent instance
agent_instance = WorkWeekHCMAgent()


class ChatRequest(BaseModel):
    message: str
    employee_id: Optional[str] = None
    mcp_token: Optional[str] = None


class TimeOffRequest(BaseModel):
    employee_id: str
    start_date: str
    end_date: str
    leave_type: str = "Vacation"
    days: float
    mcp_token: Optional[str] = None


class CancelLeaveRequest(BaseModel):
    employee_id: str
    request_id: int
    mcp_token: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    employee_id: str
    address: str
    phone: str
    mcp_token: Optional[str] = None


class GenerateMCPTokenRequest(BaseModel):
    ldap: str


@app.get("/api/auth/sso-status")
async def get_sso_status():
    """Validate corporate SSO authentication status against login.corp.google.com."""
    return validate_corp_sso()


@app.post("/api/mcp-tokens")
async def create_mcp_token(req: GenerateMCPTokenRequest):
    """Generate dynamic MCP token bound to the SSO authenticated user LDAP."""
    ldap = req.ldap.strip() if req.ldap else ""
    if not ldap:
        raise HTTPException(status_code=400, detail="Missing required 'ldap' parameter.")
    return generate_mcp_token(ldap)


@app.get("/")
async def serve_index():
    """Serve the Web GUI homepage."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index file not found.")
    return FileResponse(str(index_file))


@app.get("/api/status")
async def get_system_status(x_mcp_token: Optional[str] = Header(None)):
    """Check connectivity to WorkWeek MCP Server and resolve employee session."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        emp_id = await get_current_employee_id(mcp_token=token)
        return {
            "status": "HEALTHY",
            "agent_name": "WorkWeek HCM Agent",
            "mcp_server": {
                "endpoint": DEFAULT_MCP_URL,
                "authenticated_employee_id": emp_id.strip(),
                "connected": True,
            },
            "capabilities": [
                "get_current_employee_id",
                "get_employee_balances",
                "get_personal_info",
                "get_leave_requests",
                "request_time_off",
                "update_personal_info",
                "cancel_leave_request",
            ],
        }
    except Exception as e:
        return {
            "status": "DEGRADED",
            "agent_name": "WorkWeek HCM Agent",
            "mcp_server": {
                "endpoint": DEFAULT_MCP_URL,
                "connected": False,
                "error": str(e),
            },
        }


@app.get("/api/me/profile")
async def get_my_profile(x_mcp_token: Optional[str] = Header(None)):
    """Fetch current employee personal contact details."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        emp_id = (await get_current_employee_id(mcp_token=token)).strip()
        info_str = await get_personal_info(employee_id=emp_id, mcp_token=token)
        return {
            "employee_id": emp_id,
            "raw_output": info_str,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


@app.get("/api/me/balances")
async def get_my_balances(x_mcp_token: Optional[str] = Header(None)):
    """Fetch current leave balances for the authenticated employee."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        emp_id = (await get_current_employee_id(mcp_token=token)).strip()
        balances_str = await get_employee_balances(employee_id=emp_id, mcp_token=token)
        return {
            "employee_id": emp_id,
            "balances_text": balances_str,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch balances: {str(e)}")


@app.get("/api/me/leaves")
async def get_my_leave_history(x_mcp_token: Optional[str] = Header(None)):
    """Fetch time-off requests history."""
    token = x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        emp_id = (await get_current_employee_id(mcp_token=token)).strip()
        history_str = await get_leave_requests(employee_id=emp_id, mcp_token=token)
        return {
            "employee_id": emp_id,
            "leave_requests": history_str,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch leave history: {str(e)}")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, x_mcp_token: Optional[str] = Header(None)):
    """Process interactive chat prompt with WorkWeek HCM Agent."""
    token = req.mcp_token or x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        result = await agent_instance.run(
            user_prompt=req.message,
            employee_id=req.employee_id,
            mcp_token=token,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/leaves/request")
async def submit_leave(req: TimeOffRequest, x_mcp_token: Optional[str] = Header(None)):
    """Directly request time off."""
    token = req.mcp_token or x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        res = await request_time_off(
            employee_id=req.employee_id,
            start_date=req.start_date,
            end_date=req.end_date,
            leave_type=req.leave_type,
            days=req.days,
            mcp_token=token,
        )
        return {"result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leaves/cancel")
async def cancel_leave(req: CancelLeaveRequest, x_mcp_token: Optional[str] = Header(None)):
    """Directly cancel a leave request."""
    token = req.mcp_token or x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        res = await cancel_leave_request(
            employee_id=req.employee_id,
            request_id=req.request_id,
            mcp_token=token,
        )
        return {"result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile/update")
async def update_profile(req: UpdateProfileRequest, x_mcp_token: Optional[str] = Header(None)):
    """Directly update profile contact info."""
    token = req.mcp_token or x_mcp_token or DEFAULT_MCP_TOKEN
    try:
        res = await update_personal_info(
            employee_id=req.employee_id,
            address=req.address,
            phone=req.phone,
            mcp_token=token,
        )
        return {"result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting WorkWeek HCM Agent Web GUI at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
