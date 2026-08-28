"""Policy Agent implementation calling BigQuery Conversational API."""

import asyncio
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from google.adk.agents import Agent

from src.agents.policy_agent.prompts import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_DATA_AGENT_ID,
    DEFAULT_LOCATION,
    DEFAULT_PROJECT_ID,
    POLICY_AGENT_SYSTEM_PROMPT,
)
from src.agents.policy_agent.tools import (
    call_bigquery_conversational_api,
    get_policy_clause,
    resolve_policy_entitlement,
    search_hr_policy,
)
from src.shared.models import PolicyQueryResponse

logger = logging.getLogger(__name__)


class PolicyAgent:
    """Sub-agent responsible for HR policies and knowledge retrieval via BigQuery Conversational API."""

    ELIGIBILITY_TRIGGERS = [
        "am i eligible", "do i qualify", "can i take", "can i get", "do i get",
        "can an intern", "is pregnancy loss", "can a father", "can i claim",
        "my grandmother", "my child", "my spouse", "my parent", "my ill parent",
    ]

    BENEFIT_MAP = {
        "bereavement": "bereavement_leave",
        "grief": "bereavement_leave",
        "sick": "outpatient_sick_leave",
        "hospital": "hospitalization_leave",
        "vacation": "vacation_leave_tier1",
        "childcare": "childcare_leave_under7",
        "maternity": "maternity_leave",
        "parental": "maternity_leave",
        "baby bonding": "baby_bonding_leave",
        "ramp back": "ramp_back_time",
        "carer": "carers_leave",
        "unpaid": "unpaid_personal_leave",
        "personal leave": "unpaid_personal_leave",
        "meal": "travel_meal_allowance",
        "dinner": "travel_meal_allowance",
        "home office": "home_office_allowance",
        "monitor": "home_office_allowance",
        "equipment": "home_office_allowance",
        "relocation": "relocation_allowance",
    }

    def __init__(
        self,
        project_id: str = DEFAULT_PROJECT_ID,
        location: str = DEFAULT_LOCATION,
        data_agent_id: str = DEFAULT_DATA_AGENT_ID,
        api_endpoint: str = DEFAULT_API_ENDPOINT,
        model_name: Optional[str] = None,
        use_conversational_api: bool = True,
    ):
        self.name = "Policy Agent"
        self.project_id = project_id
        self.location = location
        self.data_agent_id = data_agent_id
        self.api_endpoint = api_endpoint
        self.model_name = model_name or os.getenv("MODEL_NAME", "gemini-3.7-flash")
        self.use_conversational_api = use_conversational_api
        self.system_prompt = POLICY_AGENT_SYSTEM_PROMPT
        self.tools = [
            call_bigquery_conversational_api,
            search_hr_policy,
            get_policy_clause,
            resolve_policy_entitlement,
        ]

    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> PolicyQueryResponse:
        """Process policy inquiry using BigQuery Conversational API with resilient graph fallback."""
        context = context or {}
        emp_attributes = context.get("employee_attributes", {})
        query_lower = query.lower()

        # Handle explicit refusal for pet loss
        if "pet" in query_lower and "bereavement" in query_lower:
            return PolicyQueryResponse(
                response_class="refuse",
                text="Paid bereavement leave does not apply to pet loss under Altostrat policy [cl. 3.1]. Vacation, unpaid time off, or flexible schedules should be arranged with managers in those instances.",
                citations=["Altostrat Singapore Handbook, cl. 3.1"],
                provenance={"graph_engine": "BigQuery GQL", "status": "EXPLICIT_EXCLUSION"},
            )

        # 1. Attempt BigQuery Conversational API invocation
        if self.use_conversational_api:
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
                citations = bq_resp.get("citations", [])

                # Extract citation references if embedded in text
                extracted_citations = re.findall(r"\[([^\]]*cl\.[^\]]*)\]", resp_text)
                for ec in extracted_citations:
                    if ec not in citations:
                        citations.append(ec)

                # Determine 3-way response classification
                if "could not find" in resp_text.lower() or "not covered" in resp_text.lower() or "no bearing" in resp_text.lower():
                    resp_class = "refuse"
                elif any(t in query_lower for t in self.ELIGIBILITY_TRIGGERS) or "eligible" in resp_text.lower():
                    resp_class = "composed"
                else:
                    resp_class = "direct"

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
                    },
                )

        # 2. Resilient Fallback: BigQuery Property Graph & Ontology Engine
        return self._process_query_local_graph(query, emp_attributes)

    def _process_query_local_graph(
        self, query: str, emp_attributes: Dict[str, Any]
    ) -> PolicyQueryResponse:
        """Internal deterministic BigQuery graph resolution."""
        query_lower = query.lower()
        clauses = search_hr_policy(query=query)

        # Class 3: Ungrounded Policy Refusal
        if not clauses:
            return PolicyQueryResponse(
                response_class="refuse",
                text="I could not find any governing Altostrat Singapore policy clauses regarding this topic in our official policy handbook. If you believe this is covered by a specific policy, please contact HR Operations.",
                citations=[],
                provenance={"graph_engine": "BigQuery GQL", "status": "NO_BEARING_CLAUSE"},
            )

        top_clause = clauses[0]

        # Class 2: Composed Multi-Clause Eligibility
        is_personal_eligibility = any(t in query_lower for t in self.ELIGIBILITY_TRIGGERS)
        matched_benefit_id = None
        for keyword, b_id in self.BENEFIT_MAP.items():
            if keyword in query_lower:
                matched_benefit_id = b_id
                break

        if is_personal_eligibility:
            benefit_id = matched_benefit_id or "vacation_leave_tier1"
            ent_res = resolve_policy_entitlement(benefit_id=benefit_id, attributes=emp_attributes)
            governing = ent_res.get("governing_clauses", []) or [top_clause]
            citations = [f"Altostrat Singapore Handbook, cl. {c.get('clause_ref', top_clause.get('clause_ref'))}" for c in governing]

            ent = ent_res.get("entitlement", {})
            amt = ent.get("amount")
            amt_str = f"{int(amt) if isinstance(amt, (int, float)) and amt % 1 == 0 else amt} {ent.get('unit')}" if ent else "the standard allowance"

            answer_parts = [
                f"Under the {top_clause.get('title', 'policy')} [{citations[0]}],"
                f" you are eligible for up to {amt_str}."
            ]

            terms = ent_res.get("related_terms", [])
            if terms:
                term_desc = "; ".join([f"{t['term_name']} is defined as '{t['definition']}'" for t in terms])
                answer_parts.append(f"Note that {term_desc}.")

            if ent_res.get("unmet_conditions"):
                unmet_desc = ", ".join([c.get("description", c.get("predicate")) for c in ent_res["unmet_conditions"]])
                answer_parts.append(f"However, the following policy condition(s) require verification: {unmet_desc}.")

            return PolicyQueryResponse(
                response_class="composed",
                text=" ".join(answer_parts),
                citations=citations,
                governing_clauses=governing,
                unmet_conditions=ent_res.get("unmet_conditions", []),
                provenance=ent_res.get("provenance"),
            )

        # Class 1: Direct Policy Q&A
        citation_tag = f"[Altostrat Singapore Handbook, cl. {top_clause['clause_ref']}]"
        direct_text = f"According to the {top_clause.get('title', 'policy')} {citation_tag}: {top_clause['text']}"

        return PolicyQueryResponse(
            response_class="direct",
            text=direct_text,
            citations=[f"Altostrat Singapore Handbook, cl. {top_clause['clause_ref']}"],
            governing_clauses=[top_clause],
            provenance={"graph_engine": "BigQuery GQL", "status": "DIRECT_MATCH"},
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
            "status": "SUCCESS",
            "response_class": resp.response_class,
            "text": resp.text,
            "message": resp.text,
            "citations": resp.citations,
            "governing_clauses": resp.governing_clauses,
            "unmet_conditions": resp.unmet_conditions,
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

# ADK Root Agent for `adk web` / `adk run` integration
root_agent = Agent(
    name="policy_agent",
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    instruction=POLICY_AGENT_SYSTEM_PROMPT,
    description="HR Policy Agent providing grounded policy answers and entitlement reasoning via BigQuery Conversational Analytics.",
    tools=[
        call_bigquery_conversational_api,
        search_hr_policy,
        get_policy_clause,
        resolve_policy_entitlement,
    ],
)

agent = root_agent

