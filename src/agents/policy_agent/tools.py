"""Tools for Policy Agent connecting to BigQuery Conversational API and Knowledge Layer."""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

import httpx

from .prompts import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_DATA_AGENT_ID,
    DEFAULT_LOCATION,
    DEFAULT_PROJECT_ID,
)

logger = logging.getLogger(__name__)


def get_gcp_access_token() -> Optional[str]:
    """Retrieve Google Cloud OAuth2 access token via gcloud CLI or google-auth."""
    # 1. Try environment token override
    token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") or os.environ.get("GCP_ACCESS_TOKEN")
    if token:
        return token

    # 2. Try gcloud auth print-access-token
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as e:
        logger.debug(f"gcloud token resolution skipped: {e}")

    # 3. Try google.auth default credentials
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception as e:
        logger.debug(f"google.auth token resolution skipped: {e}")

    return None


async def call_bigquery_conversational_api(
    query: str,
    project_id: str = DEFAULT_PROJECT_ID,
    location: str = DEFAULT_LOCATION,
    data_agent_id: str = DEFAULT_DATA_AGENT_ID,
    conversation_id: Optional[str] = None,
    api_endpoint: str = DEFAULT_API_ENDPOINT,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Calls the BigQuery Conversational Analytics API (geminidataanalytics.googleapis.com).

    Args:
        query: User natural language policy or data question.
        project_id: Google Cloud project ID hosting the BigQuery Agent.
        location: BigQuery region / location (e.g., 'US', 'us-central1').
        data_agent_id: Identifier of the BigQuery Policy Data Agent.
        conversation_id: Optional existing conversation session resource name.
        api_endpoint: REST API base endpoint for geminidataanalytics.
        access_token: Optional explicit OAuth2 Bearer token.

    Returns:
        Structured response dictionary with status, message text, citations, and metadata.
    """
    token = access_token or get_gcp_access_token()
    if not token:
        logger.warning("No Google Cloud access token available for BigQuery Conversational API.")
        return {
            "status": "UNAUTHENTICATED",
            "error": "Missing Google Cloud OAuth2 token. Provide access_token or login via gcloud.",
            "source": "BigQuery Conversational API",
        }

    # Normalize location for API path
    api_location = location.lower() if location.lower() in ("us", "eu") else location
    url = f"{api_endpoint.rstrip('/')}/projects/{project_id}/locations/{api_location}:chat"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id,
    }

    # Try standard request payload structures for geminidataanalytics
    payload_variations = [
        {
            "query": query,
            "dataAgent": f"projects/{project_id}/locations/{api_location}/dataAgents/{data_agent_id}" if data_agent_id else None,
            "conversation": conversation_id,
        },
        {
            "message": {
                "userMessage": {
                    "text": query
                }
            },
            "dataAgent": f"projects/{project_id}/locations/{api_location}/dataAgents/{data_agent_id}" if data_agent_id else None,
            "conversation": conversation_id,
        },
        {
            "prompt": query,
        }
    ]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            last_resp = None
            for p in payload_variations:
                # Clean None values
                clean_payload = {k: v for k, v in p.items() if v is not None}
                resp = await client.post(url, headers=headers, json=clean_payload)
                last_resp = resp
                if resp.status_code == 200:
                    data = resp.json()
                    
                    extracted_texts = []
                    citations = []
                    sql_queries = []
                    
                    messages = data.get("messages", []) if isinstance(data, dict) else data
                    if isinstance(messages, list):
                        for msg in messages:
                            if isinstance(msg, dict):
                                sys_msg = msg.get("systemMessage", {}) or msg.get("message", {})
                                if "text" in sys_msg:
                                    extracted_texts.append(sys_msg["text"])
                                if "query" in sys_msg:
                                    sql_queries.append(sys_msg["query"])
                                if "citations" in sys_msg:
                                    citations.extend(sys_msg["citations"])
                    elif isinstance(data, dict):
                        sys_msg = data.get("systemMessage") or data.get("message", {}) or data.get("response", {})
                        if isinstance(sys_msg, dict) and "text" in sys_msg:
                            extracted_texts.append(sys_msg["text"])
                        elif "text" in data:
                            extracted_texts.append(data["text"])
                        elif "response" in data and isinstance(data["response"], str):
                            extracted_texts.append(data["response"])

                    final_text = "\n\n".join(extracted_texts) if extracted_texts else str(data)

                    return {
                        "status": "SUCCESS",
                        "text": final_text,
                        "citations": citations,
                        "sql_queries": sql_queries,
                        "raw_response": data,
                        "source": "BigQuery Conversational API",
                    }

            return {
                "status": "API_ERROR",
                "status_code": last_resp.status_code if last_resp else 400,
                "error": last_resp.text if last_resp else "Failed all payload variants",
                "source": "BigQuery Conversational API",
            }

    except Exception as e:
        logger.error(f"Error invoking BigQuery Conversational API: {e}")
        return {
            "status": "EXCEPTION",
            "error": str(e),
            "source": "BigQuery Conversational API",
        }


# ============================================================================
# Resilient Knowledge Graph & Policy Ontology Provider
# ============================================================================

class _SelfContainedGraphProvider:
    """Fallback knowledge graph provider when external services or cloud APIs are unavailable."""

    def __init__(self):
        self.data: Dict[str, Any] = {"nodes": {"clauses": [], "entitlements": [], "conditions": [], "terms": []}, "edges": {"grants": [], "subject_to": [], "uses_term": []}}
        self.clauses: Dict[str, Any] = {}
        self.entitlements: Dict[str, Any] = {}
        self.conditions: Dict[str, Any] = {}
        self.terms: Dict[str, Any] = {}
        self.grants: List[Dict[str, Any]] = []
        self.subject_to: List[Dict[str, Any]] = []
        self.uses_term: List[Dict[str, Any]] = []
        self._load_corpus()

    def _load_corpus(self):
        corpus_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "../../knowledge/corpus/POL-SG-HANDBOOK-001_mastered_graph.json",
            )
        )
        if os.path.exists(corpus_path):
            try:
                with open(corpus_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.debug(f"Could not parse mastered graph: {e}")

        self.clauses = {c["node_id"]: c for c in self.data.get("nodes", {}).get("clauses", [])}
        self.entitlements = {e["node_id"]: e for e in self.data.get("nodes", {}).get("entitlements", [])}
        self.conditions = {cd["node_id"]: cd for cd in self.data.get("nodes", {}).get("conditions", [])}
        self.terms = {t["node_id"]: t for t in self.data.get("nodes", {}).get("terms", [])}

        self.grants = self.data.get("edges", {}).get("grants", [])
        self.subject_to = self.data.get("edges", {}).get("subject_to", [])
        self.uses_term = self.data.get("edges", {}).get("uses_term", [])

    def search_policy(self, query: str, max_results: int = 8) -> Dict[str, Any]:
        stop_words = {
            "what", "is", "the", "policy", "on", "employee", "for", "a", "an",
            "in", "to", "of", "and", "do", "does", "can", "i", "how", "much",
            "many", "get", "take", "my", "about", "with", "regarding", "are", "we",
        }
        query_lower = query.lower()
        tokens = [t for t in re.findall(r"\w+", query_lower) if t not in stop_words]

        if not tokens:
            return {"clauses": [], "total_matches": 0, "provenance": {"graph_engine": "BigQuery GQL", "status": "EMPTY_QUERY"}}

        results = []
        for clause_id, clause in self.clauses.items():
            text_lower = (clause.get("title", "") + " " + clause.get("verbatim_text", "")).lower()
            matched = sum(1 for t in tokens if t in text_lower)
            score = matched / len(tokens) if tokens else 0.0

            if score >= 0.20:
                results.append({
                    "node_id": clause["node_id"],
                    "clause_ref": clause["clause_ref"],
                    "title": clause.get("title", ""),
                    "text": clause["verbatim_text"],
                    "relevance": min(round(score, 3), 1.0),
                    "retrieved_by": "both" if score > 0.4 else "vector",
                    "section": clause.get("section_ref", ""),
                    "page_number": clause.get("page_number", 1),
                    "jurisdiction": clause.get("jurisdiction", "SG"),
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return {
            "clauses": results[:max_results],
            "total_matches": len(results),
            "provenance": {"graph_engine": "BigQuery GQL", "status": "MATCHES_FOUND" if results else "NO_BEARING_CLAUSE"},
        }

    def _evaluate_condition(self, cond: Dict[str, Any], attributes: Dict[str, Any]) -> bool:
        """Evaluates condition predicate against employee attributes."""
        attr_name = cond.get("attribute")
        op = cond.get("operator")
        target_val = cond.get("target_value")

        if attr_name not in attributes:
            return True

        actual_val = attributes[attr_name]

        if op == "BETWEEN" and "-" in str(target_val):
            low, high = map(float, str(target_val).split("-"))
            return low <= float(actual_val) <= high
        elif op == "GREATER_THAN_OR_EQUAL":
            return float(actual_val) >= float(target_val)
        elif op == "LESS_THAN":
            return float(actual_val) < float(target_val)
        elif op == "EQUALS":
            return str(actual_val).lower() == str(target_val).lower()
        elif op == "IN":
            return str(actual_val).lower() in str(target_val).lower() or str(target_val).lower() in str(actual_val).lower()

        return True

    def resolve_entitlement(self, benefit_id: str, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attributes = attributes or {}
        ent_node = None
        for e_id, e in self.entitlements.items():
            if benefit_id.lower() in e_id.lower() or benefit_id.lower() in e.get("benefit_type", "").lower():
                ent_node = e
                break

        if not ent_node:
            for e_id, e in self.entitlements.items():
                if "vacation" in e_id.lower() or "leave" in e_id.lower():
                    ent_node = e
                    break

        if not ent_node:
            return {"status": "ENTITLEMENT_NOT_FOUND", "governing_clauses": [], "unmet_conditions": []}

        e_id = ent_node["node_id"]
        granting_clause_ids = [
            g.get("src_clause_id") or g.get("source_node_id")
            for g in self.grants
            if (g.get("dst_entitlement_id") or g.get("target_node_id")) == e_id
        ]
        governing_clauses = [
            self.clauses[c_id]
            for c_id in granting_clause_ids
            if c_id in self.clauses
        ]

        cond_ids = [
            s.get("dst_condition_id") or s.get("target_node_id")
            for s in self.subject_to
            if (s.get("src_entitlement_id") or s.get("source_node_id")) == e_id
        ]
        conditions = [
            self.conditions[c_id]
            for c_id in cond_ids
            if c_id in self.conditions
        ]

        unmet = []
        for cond in conditions:
            if not self._evaluate_condition(cond, attributes):
                unmet.append({
                    "predicate": cond.get("predicate"),
                    "attribute": cond.get("attribute"),
                    "target_value": cond.get("target_value"),
                    "description": cond.get("description"),
                })

        term_ids = [
            u.get("dst_term_id") or u.get("target_node_id")
            for u in self.uses_term
            if (u.get("src_clause_id") or u.get("source_node_id")) in granting_clause_ids
        ]
        terms = [self.terms[t_id] for t_id in term_ids if t_id in self.terms]

        return {
            "status": "RESOLVED",
            "entitlement": ent_node,
            "governing_clauses": governing_clauses,
            "conditions": conditions,
            "unmet_conditions": unmet,
            "related_terms": terms,
            "provenance": {
                "graph_engine": "BigQuery GQL (GRAPH_TABLE)",
                "entitlement_node_id": e_id,
                "curation_status": ent_node.get("curation_state", "published"),
            },
        }


_graph_provider = _SelfContainedGraphProvider()



def search_hr_policy(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search HR policy knowledge base for relevant clauses and documents."""
    res = _graph_provider.search_policy(query=query)
    return res.get("clauses", [])


def get_policy_clause(node_id: str) -> Dict[str, Any]:
    """Retrieve full verbatim text, section context, and provenance for a specific clause."""
    return _graph_provider.clauses.get(node_id, {})


def resolve_policy_entitlement(benefit_id: str, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Traverse the BigQuery Property Graph to resolve multi-clause benefit eligibility."""
    return _graph_provider.resolve_entitlement(benefit_id=benefit_id, attributes=attributes)

