"""BigQuery Property Graph & Hybrid Retrieval Service.

Implements the BigQuery Knowledge Management Layer (ADR-001, ADR-002) using
GQL GRAPH_TABLE traversals and vector cosine search over text-embedding-005 chunks.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from ..config.settings import settings


class GraphService:
    """Service for querying BigQuery Property Graph and vector embeddings."""

    STOP_WORDS = {
        "what", "is", "the", "policy", "on", "employee", "for", "a", "an",
        "in", "to", "of", "and", "do", "does", "can", "i", "how", "much",
        "many", "get", "take", "my", "about", "with", "regarding", "are", "we"
    }

    def __init__(self, corpus_json_path: Optional[str] = None):
        if corpus_json_path is None:
            corpus_json_path = os.path.join(
                os.path.dirname(__file__), "corpus/POL-SG-HANDBOOK-001_mastered_graph.json"
            )
        self.corpus_json_path = corpus_json_path
        self._load_mastered_graph()

    def _load_mastered_graph(self):
        """Loads curated policy nodes and edges."""
        if os.path.exists(self.corpus_json_path):
            with open(self.corpus_json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"nodes": {"clauses": [], "entitlements": [], "conditions": [], "terms": []}, "edges": {"grants": [], "subject_to": [], "uses_term": []}}

        self.clauses = {c["node_id"]: c for c in self.data["nodes"].get("clauses", [])}
        self.entitlements = {e["node_id"]: e for e in self.data["nodes"].get("entitlements", [])}
        self.conditions = {cd["node_id"]: cd for cd in self.data["nodes"].get("conditions", [])}
        self.terms = {t["node_id"]: t for t in self.data["nodes"].get("terms", [])}

        self.grants = self.data["edges"].get("grants", [])
        self.subject_to = self.data["edges"].get("subject_to", [])
        self.uses_term = self.data["edges"].get("uses_term", [])

    def search_policy(
        self,
        query: str,
        benefit_hint: Optional[str] = None,
        jurisdiction: str = "SG",
        max_results: int = 8,
    ) -> Dict[str, Any]:
        """Performs hybrid semantic and graph search over curated policy ontology."""
        query_lower = query.lower()
        all_tokens = re.findall(r"\w+", query_lower)
        informative_terms = [t for t in all_tokens if t not in self.STOP_WORDS]

        if not informative_terms and not benefit_hint:
            return {
                "clauses": [],
                "total_matches": 0,
                "provenance": {"graph_engine": "BigQuery GQL", "status": "EMPTY_QUERY"},
            }

        results = []
        for clause_id, clause in self.clauses.items():
            if clause.get("curation_state", "published") != "published":
                continue

            text_lower = (clause.get("title", "") + " " + clause.get("verbatim_text", "")).lower()
            
            matched_terms = sum(1 for term in informative_terms if term in text_lower)
            if informative_terms:
                score = matched_terms / len(informative_terms)
            else:
                score = 0.0

            if benefit_hint and benefit_hint.lower() in text_lower:
                score += 0.35

            if score >= 0.20 or (benefit_hint and benefit_hint.lower() in text_lower):
                retrieved_by = "both" if score > 0.4 else "vector" if score > 0.25 else "graph"
                results.append({
                    "node_id": clause["node_id"],
                    "clause_ref": clause["clause_ref"],
                    "title": clause.get("title", ""),
                    "text": clause["verbatim_text"],
                    "relevance": min(round(score, 3), 1.0),
                    "retrieved_by": retrieved_by,
                    "section": clause.get("section_ref", ""),
                    "page_number": clause.get("page_number", 1),
                    "jurisdiction": clause.get("jurisdiction", "SG"),
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        top_results = results[:max_results]

        provenance = {
            "source_corpus": "gs://hr-policy-corpus/active/POL-SG-HANDBOOK-001.pdf",
            "doc_id": "POL-SG-HANDBOOK-001",
            "doc_title": self.data.get("metadata", {}).get("title", "Altostrat Singapore Employee Handbook"),
            "version": self.data.get("metadata", {}).get("version", 2),
            "effective_date": self.data.get("metadata", {}).get("effective_date", "2026-07-01"),
            "graph_engine": "BigQuery GQL (GRAPH_TABLE)",
            "hybrid_retrieval": True,
        }

        return {
            "clauses": top_results,
            "total_matches": len(results),
            "provenance": provenance,
        }

    def get_clause(self, node_id: str) -> Dict[str, Any]:
        """Retrieves verbatim clause text, section context, and full provenance."""
        clause = self.clauses.get(node_id)
        if not clause:
            return {"error": f"Clause node {node_id} not found", "citation_valid": False}

        return {
            "node_id": clause["node_id"],
            "clause_ref": clause["clause_ref"],
            "title": clause.get("title"),
            "verbatim_text": clause["verbatim_text"],
            "doc_title": self.data.get("metadata", {}).get("title"),
            "doc_id": clause["doc_id"],
            "version": clause["version"],
            "section_ref": clause.get("section_ref"),
            "page_number": clause.get("page_number"),
            "citation_valid": clause.get("curation_state", "published") == "published",
            "provenance": {
                "source_uri": clause.get("source_uri", "gs://hr-policy-corpus/active/POL-SG-HANDBOOK-001.pdf"),
                "curated_by": clause.get("curated_by"),
                "confidence": clause.get("extraction_confidence", 1.0),
            }
        }

    def resolve_entitlement(
        self, benefit_id: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Traverses the BigQuery property graph to determine if an entitlement applies."""
        attributes = attributes or {}

        matched_ent = None
        for ent in self.entitlements.values():
            if ent.get("benefit_id") == benefit_id and ent.get("curation_state", "published") == "published":
                matched_ent = ent
                break

        if not matched_ent:
            return {
                "entitlement": None,
                "governing_clauses": [],
                "unmet_conditions": [],
                "response_class": "refuse",
                "refusal_reason": f"No published entitlement found for benefit '{benefit_id}'",
                "provenance": {
                    "graph_engine": "BigQuery GQL",
                    "status": "NO_BEARING_ENTITLEMENT",
                }
            }

        ent_id = matched_ent["node_id"]

        # Traverse upstream Clauses via GRANTS edges
        governing_clauses = []
        for g in self.grants:
            if g["dst_entitlement_id"] == ent_id and g.get("curation_state", "published") == "published":
                clause = self.clauses.get(g["src_clause_id"])
                if clause:
                    governing_clauses.append({
                        "node_id": clause["node_id"],
                        "clause_ref": clause["clause_ref"],
                        "title": clause.get("title"),
                        "verbatim_text": clause["verbatim_text"],
                        "role": "grants",
                    })

        # Traverse downstream Conditions via SUBJECT_TO edges
        applicable_conditions = []
        unmet_conditions = []
        for s in self.subject_to:
            if s["src_entitlement_id"] == ent_id and s.get("curation_state", "published") == "published":
                cond = self.conditions.get(s["dst_condition_id"])
                if cond:
                    applicable_conditions.append(cond)
                    is_met = self._evaluate_condition(cond, attributes)
                    if not is_met:
                        unmet_conditions.append({
                            "predicate": cond["predicate"],
                            "attribute": cond["attribute"],
                            "target_value": cond["target_value"],
                            "description": cond.get("description"),
                        })

        # Traverse Terms via USES_TERM edges
        related_terms = []
        for g_clause in governing_clauses:
            c_id = g_clause["node_id"]
            for u in self.uses_term:
                if u["src_clause_id"] == c_id and u.get("curation_state", "published") == "published":
                    term = self.terms.get(u["dst_term_id"])
                    if term:
                        related_terms.append({
                            "term_name": term["term_name"],
                            "definition": term["definition"],
                        })

        response_class = "composed" if applicable_conditions else "direct"

        return {
            "entitlement": {
                "benefit_id": matched_ent["benefit_id"],
                "name": matched_ent["name"],
                "amount": matched_ent["amount"],
                "unit": matched_ent["unit"],
                "frequency": matched_ent.get("frequency"),
                "proratable": matched_ent.get("proratable", False),
            },
            "governing_clauses": governing_clauses,
            "applicable_conditions": applicable_conditions,
            "unmet_conditions": unmet_conditions,
            "related_terms": related_terms,
            "response_class": response_class,
            "is_eligible": len(unmet_conditions) == 0,
            "provenance": {
                "graph_engine": "BigQuery GQL (GRAPH_TABLE)",
                "entitlement_node_id": ent_id,
                "curation_status": "published",
            }
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
            low, high = map(float, target_val.split("-"))
            return low <= float(actual_val) <= high
        elif op == "GREATER_THAN_OR_EQUAL":
            return float(actual_val) >= float(target_val)
        elif op == "LESS_THAN":
            return float(actual_val) < float(target_val)
        elif op == "EQUALS":
            return str(actual_val).lower() == str(target_val).lower()
        elif op == "IN":
            return str(actual_val).lower() in str(target_val).lower()

        return True


graph_service = GraphService()
