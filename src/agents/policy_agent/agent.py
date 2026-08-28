"""Policy Agent implementation calling BigQuery Conversational API exclusively."""

import asyncio
import logging
import os
import re
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.agents.policy_agent.prompts import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_DATA_AGENT_ID,
    DEFAULT_LOCATION,
    DEFAULT_PROJECT_ID,
)
from src.agents.policy_agent.tools import call_bigquery_conversational_api
from src.shared.models import PolicyQueryResponse

logger = logging.getLogger(__name__)


class PolicyAgent(BaseAgent):
    """Sub-agent responsible for HR policies exclusively via BigQuery Conversational Analytics."""

    project_id: str = DEFAULT_PROJECT_ID
    location: str = DEFAULT_LOCATION
    data_agent_id: str = DEFAULT_DATA_AGENT_ID
    api_endpoint: str = DEFAULT_API_ENDPOINT

    def __init__(
        self,
        name: str = "policy_agent",
        description: str = "HR Policy Agent answering questions exclusively via BigQuery Conversational Analytics.",
        project_id: str = DEFAULT_PROJECT_ID,
        location: str = DEFAULT_LOCATION,
        data_agent_id: str = DEFAULT_DATA_AGENT_ID,
        api_endpoint: str = DEFAULT_API_ENDPOINT,
        **kwargs: Any,
    ):
        super().__init__(
            name=name,
            description=description,
            project_id=project_id,
            location=location,
            data_agent_id=data_agent_id,
            api_endpoint=api_endpoint,
            **kwargs,
        )

    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> PolicyQueryResponse:
        """Process policy inquiry exclusively using BigQuery Conversational API."""
        bq_resp = await call_bigquery_conversational_api(
            query=query,
            project_id=self.project_id,
            location=self.location,
            data_agent_id=self.data_agent_id,
            conversation_id=session_id,
            api_endpoint=self.api_endpoint,
            access_token=access_token,
        )

        if bq_resp.get("status") == "SUCCESS" and bq_resp.get("text"):
            resp_text = bq_resp["text"]
            citations = list(bq_resp.get("citations", []))

            # Extract citation references if embedded in text
            extracted_citations = re.findall(r"\[([^\]]*cl\.[^\]]*)\]", resp_text)
            for ec in extracted_citations:
                if ec not in citations:
                    citations.append(ec)

            query_lower = query.lower()
            text_lower = resp_text.lower()
            if (
                "could not find" in text_lower
                or "not covered" in text_lower
                or "no bearing" in text_lower
            ):
                resp_class = "refuse"
            elif "eligible" in query_lower or "eligible" in text_lower or "qualify" in query_lower:
                resp_class = "composed"
            else:
                resp_class = "direct"

            # Attach hyperlinked source Cloud Storage document with page deep-linking
            source_doc = bq_resp.get("source_document") or {}
            source_link = source_doc.get("markdown_link")
            if source_link and resp_class != "refuse":
                if source_link not in resp_text:
                    resp_text = f"{resp_text}\n\n📄 **Source Document:** {source_link}"

            return PolicyQueryResponse(
                response_class=resp_class,
                text=resp_text,
                citations=citations,
                provenance={
                    "engine": "BigQuery Conversational API",
                    "data_agent_id": self.data_agent_id,
                    "project_id": self.project_id,
                    "location": self.location,
                    "sql_queries": bq_resp.get("sql_queries", []),
                    "source_document": source_doc,
                    "pages": bq_resp.get("pages", []),
                },
            )

        # Handle API errors / Unauthenticated
        error_msg = bq_resp.get("error") or bq_resp.get("status", "BIGQUERY_CA_ERROR")
        return PolicyQueryResponse(
            response_class="refuse",
            text=f"BigQuery Conversational Agent Error: {error_msg}",
            citations=[],
            provenance={
                "engine": "BigQuery Conversational API",
                "status": bq_resp.get("status"),
                "error": error_msg,
            },
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """ADK execution entrypoint for adk web / adk run."""
        user_text = ""
        if ctx.session and ctx.session.events:
            for ev in reversed(ctx.session.events):
                if ev.content and ev.content.role == "user" and ev.content.parts:
                    for p in ev.content.parts:
                        if p.text:
                            user_text = p.text
                            break
                if user_text:
                    break

        if not user_text:
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="Please provide a policy question.")],
                ),
            )
            return

        policy_res = await self.process_query(
            query=user_text,
            session_id=ctx.session.id if ctx.session else None,
        )

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=policy_res.text)],
            ),
        )

    def process_policy_query(
        self, query: str, employee_attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synchronous helper for evaluation suites and benchmarks."""
        resp = asyncio.run(
            self.process_query(
                query=query, context={"employee_attributes": employee_attributes or {}}
            )
        )
        return {
            "status": "SUCCESS" if resp.response_class != "refuse" or "Error:" not in resp.text else "ERROR",
            "response_class": resp.response_class,
            "text": resp.text,
            "message": resp.text,
            "citations": resp.citations,
            "provenance": resp.provenance,
        }

    def handle_message(
        self,
        session_id: str,
        user_message: str,
        principal_email: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Standard supervisor / orchestrator message handler."""
        ctx = context or {}
        if principal_email and "employee_attributes" not in ctx:
            ctx["employee_attributes"] = {"principal_email": principal_email}

        resp = asyncio.run(
            self.process_query(query=user_message, context=ctx, session_id=session_id)
        )
        return {
            "status": "SUCCESS",
            "session_id": session_id,
            "response_class": resp.response_class,
            "message": resp.text,
            "citations": resp.citations,
            "provenance": resp.provenance,
        }


policy_agent = PolicyAgent()
root_agent = policy_agent
agent = policy_agent

