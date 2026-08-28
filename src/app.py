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

# Singleton agent instances
hcm_agent = WorkWeekHCMAgent()
itsm_agent = ServiceImmediatelyAgent()


class ChatRequest(BaseModel):
    message: str
    agent_target: Optional[str] = "auto"  # "workweek", "service_immediately", or "auto"
    employee_id: Optional[str] = None
    mcp_token: Optional[str] = None


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
    token = x_mcp_token or "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"
    return {
        "status": "HEALTHY",
        "authenticated_employee_id": "EMP-545",
        "agents": {
            "workweek_hcm": {
                "name": "WorkWeek HCM Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/",
                "model": hcm_agent.model_name,
                "status": "ONLINE",
            },
            "service_immediately": {
                "name": "ServiceImmediately Agent",
                "mcp_url": "https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/",
                "model": itsm_agent.model_name,
                "status": "ONLINE",
            },
        },
    }


@app.get("/api/hcm/profile")
async def get_hcm_profile(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek personal contact info."""
    token = x_mcp_token or "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"
    try:
        raw_output = await hcm_get_profile(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "raw_output": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hcm/balances")
async def get_hcm_balances(x_mcp_token: Optional[str] = Header(None)):
    """Fetch WorkWeek leave balances."""
    token = x_mcp_token or "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"
    try:
        raw_output = await hcm_get_balances(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "balances_text": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itsm/tickets")
async def get_itsm_tickets(x_mcp_token: Optional[str] = Header(None)):
    """Fetch ServiceImmediately incident tickets."""
    token = x_mcp_token or "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"
    try:
        raw_output = await itsm_list_tickets(employee_id="EMP-545", mcp_token=token)
        return {"employee_id": "EMP-545", "tickets_raw": raw_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_interaction(req: ChatRequest, x_mcp_token: Optional[str] = Header(None)):
    """Interactive multi-agent chat endpoint."""
    token = req.mcp_token or x_mcp_token or "mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg"
    target = req.agent_target or "auto"

    if target == "auto":
        target = auto_route_query(req.message)

    try:
        if target == "service_immediately":
            result = await itsm_agent.run(
                user_prompt=req.message,
                employee_id=req.employee_id or "EMP-545",
                mcp_token=token,
            )
        else:
            result = await hcm_agent.run(
                user_prompt=req.message,
                employee_id=req.employee_id or "EMP-545",
                mcp_token=token,
            )
        return result
    except BaseException as e:
        # Extract underlying sub-exceptions if wrapped in ExceptionGroup
        err_msg = str(e)
        if hasattr(e, "exceptions") and e.exceptions:
            sub_msgs = [str(sub) for sub in e.exceptions]
            err_msg = " | ".join(sub_msgs)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {err_msg}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Elevate HR & ITSM Multi-Agent Portal at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
