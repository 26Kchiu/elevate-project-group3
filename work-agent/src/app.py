"""
FastAPI Server & Web GUI Backend for WorkAgent.
Serves interactive REST API, Harry Lin identity enforcement, and static web UI assets.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, Optional, List

from src.agent import orchestrator, submit_my_leave_request, update_my_contact_info
from src.workweek_service import workweek_client
from src.security import confirmation_manager

app = FastAPI(
    title="WorkAgent - WorkWeek HCM Virtual Assistant",
    description="Enterprise AI Conversational Agent for WorkWeek SaaS (Google ADK & Gemini)",
    version="1.0.0"
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
    user_id: str = "harrylin"
    message: str
    mcp_token: Optional[str] = None


class DirectConfirmRequest(BaseModel):
    action: str
    confirmation_token: str
    payload: Dict[str, Any]
    mcp_token: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    await workweek_client.initialize()


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(str(index_file))


@app.get("/api/status")
async def get_system_status():
    """Returns connectivity, active user, and health status."""
    return {
        "status": "HEALTHY",
        "agent": "WorkAgent (WorkWeek HCM Specialist)",
        "model": "Gemini 2.5 Flash / 3.7 Flash",
        "authenticated_user": {
            "name": "Harry Lin",
            "email": "harrylin@google.com",
            "employee_id": "EMP-HL-001",
            "role": "Customer Engineer & Enterprise Solutions Architect",
            "subject_isolation": "ENFORCED (Self-Only Access)"
        },
        "workweek_service": {
            "endpoint": workweek_client.base_url,
            "mode": workweek_client.connected_mode,
            "token_configured": bool(workweek_client.mcp_token)
        },
        "supported_tools": [
            "get_my_employee_profile",
            "get_my_leave_balances",
            "get_my_leave_request_status",
            "stage_my_leave_request",
            "submit_my_leave_request",
            "stage_my_contact_update",
            "update_my_contact_info"
        ]
    }


@app.get("/api/me/profile")
async def get_my_profile():
    return await workweek_client.get_employee_profile("EMP-HL-001")


@app.get("/api/me/balances")
async def get_my_balances():
    return await workweek_client.get_leave_balances("EMP-HL-001")


@app.post("/api/chat")
async def chat_interaction(req: ChatRequest):
    """Processes interactive conversational message with WorkAgent."""
    try:
        response = await orchestrator.process_user_message(
            user_id=req.user_id,
            message_text=req.message,
            authenticated_employee_id="EMP-HL-001",
            user_mcp_token=req.mcp_token
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/confirm")
async def confirm_action(req: DirectConfirmRequest):
    """Directly confirms and commits a staged action using the cryptographic token."""
    if req.action == "submit_leave_request":
        res = await submit_my_leave_request(
            leave_type=req.payload.get("leave_type", "Vacation"),
            start_date=req.payload.get("start_date", ""),
            end_date=req.payload.get("end_date", ""),
            half_day=req.payload.get("half_day", False),
            note=req.payload.get("note", ""),
            confirmation_token=req.confirmation_token
        )
        return res
    elif req.action == "update_contact_info":
        res = await update_my_contact_info(
            phone=req.payload.get("phone"),
            address=req.payload.get("address"),
            emergency_contact=req.payload.get("emergency_contact"),
            confirmation_token=req.confirmation_token
        )
        return res
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
