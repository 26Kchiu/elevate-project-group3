"""
FastAPI Server & Web GUI Backend for WorkAgent.
Serves REST API, MCP token session forwarding, and dynamic profile retrieval.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, Optional, List

from src.agent import orchestrator, submit_time_off_request, submit_personal_info_update
from src.workweek_service import workweek_mcp
from src.security import confirmation_manager

app = FastAPI(
    title="WorkAgent - WorkWeek MCP Virtual Assistant",
    description="Enterprise Conversational Agent connecting to WorkWeek MCP Server (/work-week/mcp/)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    user_id: str = "default_user"
    message: str
    mcp_token: Optional[str] = None


class DirectConfirmRequest(BaseModel):
    action: str
    confirmation_token: str
    payload: Dict[str, Any]
    mcp_token: Optional[str] = None


@app.get("/")
async def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
async def get_system_status(x_mcp_token: Optional[str] = Header(None)):
    token = x_mcp_token or workweek_mcp.default_token
    emp_res = await workweek_mcp.get_current_employee_id(token)
    return {
        "status": "HEALTHY",
        "agent": "WorkAgent (WorkWeek MCP Domain Agent)",
        "mcp_server": {
            "endpoint": f"{workweek_mcp.base_url}/work-week/mcp/",
            "mode": workweek_mcp.connected_mode,
            "authenticated_employee_id": emp_res["employee_id"]
        },
        "capabilities": {
            "resources": [
                "workweek://employees/{employee_id}/profile",
                "workweek://employees/{employee_id}/timeoff"
            ],
            "tools": [
                "get_current_employee_id",
                "get_employee_balances",
                "request_time_off",
                "update_personal_info",
                "get_personal_info",
                "get_leave_requests",
                "cancel_leave_request"
            ]
        }
    }


@app.get("/api/me/profile")
async def get_my_profile(x_mcp_token: Optional[str] = Header(None)):
    token = x_mcp_token or workweek_mcp.default_token
    emp_res = await workweek_mcp.get_current_employee_id(token)
    return await workweek_mcp.read_resource_profile(emp_res["employee_id"], token)


@app.get("/api/me/balances")
async def get_my_balances(x_mcp_token: Optional[str] = Header(None)):
    token = x_mcp_token or workweek_mcp.default_token
    emp_res = await workweek_mcp.get_current_employee_id(token)
    return await workweek_mcp.get_employee_balances(emp_res["employee_id"], token)


@app.post("/api/chat")
async def chat_interaction(req: ChatRequest, x_mcp_token: Optional[str] = Header(None)):
    token = req.mcp_token or x_mcp_token or workweek_mcp.default_token
    try:
        response = await orchestrator.process_user_message(
            user_id=req.user_id,
            message_text=req.message,
            mcp_token=token
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/confirm")
async def confirm_action(req: DirectConfirmRequest, x_mcp_token: Optional[str] = Header(None)):
    token = req.mcp_token or x_mcp_token or workweek_mcp.default_token
    if req.action in ["request_time_off", "submit_leave_request"]:
        res = await submit_time_off_request(
            leave_type=req.payload.get("leave_type", "vacation"),
            start_date=req.payload.get("start_date", ""),
            end_date=req.payload.get("end_date", ""),
            days=float(req.payload.get("days", 1.0)),
            confirmation_token=req.confirmation_token
        )
        return res
    elif req.action in ["update_personal_info", "update_contact_info"]:
        res = await submit_personal_info_update(
            address=req.payload.get("address", ""),
            phone=req.payload.get("phone", ""),
            confirmation_token=req.confirmation_token
        )
        return res
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
