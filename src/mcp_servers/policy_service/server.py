"""Policy Service MCP Server implementation for BigQuery Knowledge Graph."""
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.knowledge.graph_service import graph_service


class PolicyServiceMCPServer:
    """MCP Server exposing BigQuery Knowledge Graph tools to agents."""

    def __init__(self):
        self.service_name = "policy-service-mcp"

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools exposed by Policy MCP Server."""
        return [
            {
                "name": "policy_search",
                "description": "Hybrid semantic and BigQuery graph search over curated policy ontology.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query or natural language question"},
                        "jurisdiction": {"type": "string", "default": "SG"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "policy_get_clause",
                "description": "Retrieve verbatim text and provenance for a specific policy clause.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "Unique identifier of clause node"}
                    },
                    "required": ["node_id"]
                }
            },
            {
                "name": "policy_resolve_entitlement",
                "description": "Traverse BigQuery Property Graph to resolve multi-clause benefit entitlements and conditions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "benefit_id": {"type": "string", "description": "Entitlement benefit identifier"},
                        "attributes": {"type": "object", "description": "Employee attributes for condition predicates"}
                    },
                    "required": ["benefit_id"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call against the Knowledge Graph service."""
        if tool_name == "policy_search":
            return graph_service.search_policy(query=arguments.get("query", ""))
        elif tool_name == "policy_get_clause":
            return graph_service.get_clause(node_id=arguments.get("node_id", ""))
        elif tool_name == "policy_resolve_entitlement":
            return graph_service.resolve_entitlement(
                benefit_id=arguments.get("benefit_id", ""),
                attributes=arguments.get("attributes")
            )
        else:
            return {"error": f"Tool '{tool_name}' not found on {self.service_name}"}


policy_mcp_server = PolicyServiceMCPServer()
