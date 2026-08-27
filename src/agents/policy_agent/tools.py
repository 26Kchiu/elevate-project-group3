"""Tools for Policy Agent connecting to BigQuery Knowledge Graph."""
import os
import sys
from typing import Any, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.knowledge.graph_service import graph_service


def search_hr_policy(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search HR policy knowledge base for relevant clauses and documents.
    
    Args:
        query: User policy question or keyword search
        category: Optional policy section filter
        
    Returns:
        List of matching policy clauses with relevance scores and provenance.
    """
    res = graph_service.search_policy(query=query)
    return res.get("clauses", [])


def get_policy_clause(node_id: str) -> Dict[str, Any]:
    """Retrieve full verbatim text, section context, and provenance for a specific clause.
    
    Args:
        node_id: Unique identifier of clause node (e.g., 'CLAUSE-SG-1.1-01')
        
    Returns:
        Clause dictionary with verbatim text, section ref, and citation status.
    """
    return graph_service.get_clause(node_id=node_id)


def resolve_policy_entitlement(benefit_id: str, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Traverse the BigQuery Property Graph to resolve multi-clause benefit eligibility.
    
    Args:
        benefit_id: Entitlement benefit identifier (e.g., 'bereavement_leave', 'vacation_leave_tier1')
        attributes: Employee attributes for evaluating condition predicates (e.g. tenure, relationship)
        
    Returns:
        Entitlement resolution result with governing clauses, unmet conditions, and related terms.
    """
    return graph_service.resolve_entitlement(benefit_id=benefit_id, attributes=attributes)
