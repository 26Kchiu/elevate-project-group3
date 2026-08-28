"""Root Orchestrator implementation coordinating Policy, HCM, and ITSM agents."""

import logging
import os
from typing import Any, Dict, Optional

from src.agents.policy_agent import PolicyAgent
from src.agents.service_immediately_agent import ServiceImmediatelyAgent
from src.agents.workweek_hcm_agent import WorkWeekHCMAgent
from .prompts import ROOT_ORCHESTRATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def classify_intent(query: str) -> str:
    """Classify user intent into one of three specialist agents."""
    q_lower = query.lower()

    # 1. ITSM / Hardware / Software Ticket Intent -> ServiceImmediately Agent
    itsm_keywords = [
        "ticket", "incident", "it support", "laptop", "hardware", "software",
        "vpn", "network", "access", "iam", "password", "screen", "monitor",
        "keyboard", "service desk", "inc00", "repair", "itil", "crash", "bug",
        "工單", "報修", "電腦", "硬體", "軟體", "螢幕", "鍵盤", "網路", "密碼", "it支援"
    ]
    for kw in itsm_keywords:
        if kw in q_lower:
            return "service_immediately"

    # 2. General Company Policy & Handbook Rules -> Policy Agent
    policy_keywords = [
        "policy", "handbook", "rule", "guideline", "clause", "entitled",
        "eligible", "eligibility", "maternity", "paternity", "bereavement",
        "sabbatical", "expense reimbursement", "hospitalization", "code of conduct",
        "medical leave", "outpatient", "insurance", "allowance", "overtime",
        "政策", "手冊", "規定", "辦法", "資格", "育嬰假", "產假", "喪假", "公假",
        "報銷規定", "合規", "福利手冊", "員工守則", "保險", "補助", "津貼", "病假規定"
    ]
    for kw in policy_keywords:
        if kw in q_lower:
            return "policy"

    # 3. Personal Operations (Checking Personal Balance, Submitting Leave, Updating Profile) -> WorkWeek HCM Agent
    return "workweek"


class RootOrchestrator:
    """Master agent coordinating sub-agents: Policy, WorkWeek HCM, and ServiceImmediately."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        model_name: str = "auto",
        employee_id: str = "EMP-545",
    ):
        self.name = "Root Orchestrator"
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "elevate-taiwan-cohort-2")
        self.model_name = model_name
        self.employee_id = employee_id
        self.system_prompt = ROOT_ORCHESTRATOR_SYSTEM_PROMPT

        self.policy_agent = PolicyAgent(project_id=self.project_id)
        self.hcm_agent = WorkWeekHCMAgent()
        self.itsm_agent = ServiceImmediatelyAgent(model_name=self.model_name, employee_id=self.employee_id)

    async def route_and_execute(
        self,
        user_query: str,
        target: Optional[str] = "auto",
        employee_id: Optional[str] = None,
        mcp_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Route user inquiry to appropriate sub-agent and return formatted result."""
        emp_id = employee_id or self.employee_id
        selected_target = target if target and target != "auto" else classify_intent(user_query)

        logger.info(f"[Root Orchestrator] Routing query to specialist: '{selected_target}'")

        if selected_target == "policy":
            resp = await self.policy_agent.process_query(query=user_query)
            return {
                "agent_name": "Policy Agent",
                "model": "BigQuery Conversational Analytics",
                "reply": resp.text,
                "response_class": resp.response_class,
                "citations": resp.citations,
                "provenance": resp.provenance,
                "employee_id": emp_id,
                "tool_calls": [],
                "tool_responses": [],
            }

        elif selected_target == "service_immediately":
            return await self.itsm_agent.run(
                user_prompt=user_query,
                employee_id=emp_id,
                mcp_token=mcp_token,
            )

        else:
            # Default to WorkWeek HCM Agent
            return await self.hcm_agent.run(
                user_prompt=user_query,
                employee_id=emp_id,
                mcp_token=mcp_token,
            )
