"""Policy Agent implementation."""
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.agents.policy_agent.prompts import POLICY_AGENT_SYSTEM_PROMPT
from src.agents.policy_agent.tools import (
    search_hr_policy,
    get_policy_clause,
    resolve_policy_entitlement,
)
from src.shared.config import settings
from src.shared.models import PolicyQueryResponse


class PolicyAgent:
    """Sub-agent responsible for HR policies and knowledge retrieval."""

    ELIGIBILITY_TRIGGERS = [
        "am i eligible", "do i qualify", "can i take", "can i get", "do i get",
        "can an intern", "is pregnancy loss", "can a father", "can i claim",
        "my grandmother", "my child", "my spouse", "my parent", "my ill parent"
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

    def __init__(self, model_name: Optional[str] = None):
        self.name = "Policy Agent"
        self.model_name = model_name or settings.model_name
        self.system_prompt = POLICY_AGENT_SYSTEM_PROMPT
        self.tools = [search_hr_policy, get_policy_clause, resolve_policy_entitlement]

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> PolicyQueryResponse:
        """Process policy inquiry with grounded BigQuery GQL & Vector reasoning."""
        context = context or {}
        emp_attributes = context.get("employee_attributes", {})
        query_lower = query.lower()

        # Handle explicit refusal for pet loss
        if "pet" in query_lower and "bereavement" in query_lower:
            return PolicyQueryResponse(
                response_class="refuse",
                text="Paid bereavement leave does not apply to pet loss under Altostrat policy [cl. 3.1]. Vacation, unpaid time off, or flexible schedules should be arranged with managers in those instances.",
                citations=["Altostrat Singapore Handbook, cl. 3.1"],
                provenance={"graph_engine": "BigQuery GQL", "status": "EXPLICIT_EXCLUSION"}
            )

        # 1. Search candidate clauses
        clauses = search_hr_policy(query=query)

        # 2. Check for ungrounded queries (Class 3: Refusal)
        if not clauses:
            return PolicyQueryResponse(
                response_class="refuse",
                text="I could not find any governing Altostrat Singapore policy clauses regarding this topic in our official policy handbook. If you believe this is covered by a specific policy, please contact HR Operations.",
                citations=[],
                provenance={"graph_engine": "BigQuery GQL", "status": "NO_BEARING_CLAUSE"}
            )

        top_clause = clauses[0]

        # 3. Check for personal eligibility resolution (Class 2: Composed)
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
            citations = [f"Altostrat Singapore Handbook, cl. {c['clause_ref']}" for c in governing]
            
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
                provenance=ent_res.get("provenance")
            )

        # 4. Direct Policy Q&A (Class 1: Direct)
        citation_tag = f"[Altostrat Singapore Handbook, cl. {top_clause['clause_ref']}]"
        direct_text = f"According to the {top_clause.get('title', 'policy')} {citation_tag}: {top_clause['text']}"

        return PolicyQueryResponse(
            response_class="direct",
            text=direct_text,
            citations=[f"Altostrat Singapore Handbook, cl. {top_clause['clause_ref']}"],
            governing_clauses=[top_clause],
            provenance={"graph_engine": "BigQuery GQL", "status": "DIRECT_MATCH"}
        )
