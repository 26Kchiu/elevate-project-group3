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
    DEFAULT_POLICY_DOCUMENT_BASE_URL,
    DEFAULT_POLICY_DOCUMENT_BUCKET,
    DEFAULT_POLICY_DOCUMENT_PATH,
    DEFAULT_PROJECT_ID,
)

logger = logging.getLogger(__name__)


def build_source_document_link(
    pages: Optional[List[int]] = None,
    base_url: Optional[str] = None,
    title: str = "Altostrat Singapore Employee Handbook",
) -> Dict[str, Any]:
    """Constructs a Google Cloud Storage direct deep-link to the policy document and page."""
    url_base = base_url or DEFAULT_POLICY_DOCUMENT_BASE_URL
    unique_pages = sorted(list(set(pages))) if pages else []

    if unique_pages:
        first_page = unique_pages[0]
        url = f"{url_base}#page={first_page}"
        if len(unique_pages) == 1:
            label = f"{title} (Page {first_page})"
        else:
            pages_str = ", ".join(str(p) for p in unique_pages)
            label = f"{title} (Pages {pages_str})"
    else:
        url = url_base
        label = title

    markdown_link = f"[{label}]({url})"
    return {
        "url": url,
        "label": label,
        "markdown_link": markdown_link,
        "pages": unique_pages,
        "gcs_uri": f"gs://{DEFAULT_POLICY_DOCUMENT_BUCKET}/{DEFAULT_POLICY_DOCUMENT_PATH}",
    }


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

    payload = {
        "parent": f"projects/{project_id}/locations/{api_location}",
        "messages": [
            {
                "userMessage": {
                    "text": query
                }
            }
        ],
    }
    if data_agent_id:
        # Check if data_agent_id already contains full resource name
        if "/" in data_agent_id:
            agent_resource = data_agent_id
        else:
            agent_resource = f"projects/{project_id}/locations/{api_location}/dataAgents/{data_agent_id}"
        payload["dataAgentContext"] = {"dataAgent": agent_resource}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()

                extracted_texts = []
                citations = []
                sql_queries = []
                detected_pages = set()

                items = data if isinstance(data, list) else data.get("messages", [data])
                for item in items:
                    if isinstance(item, dict):
                        sys_msg = item.get("systemMessage", {})
                        text_obj = sys_msg.get("text", {})
                        if isinstance(text_obj, dict):
                            parts = text_obj.get("parts", [])
                            text_type = text_obj.get("textType")
                            if text_type == "FINAL_RESPONSE" and parts:
                                extracted_texts.extend(parts)
                        elif isinstance(text_obj, str):
                            extracted_texts.append(text_obj)

                        # Extract SQL and table rows
                        data_block = sys_msg.get("data", {})
                        if isinstance(data_block, dict):
                            if "generatedSql" in data_block:
                                sql_queries.append(data_block["generatedSql"])
                            if "result" in data_block and isinstance(data_block["result"], dict):
                                rows = data_block["result"].get("data", [])
                                for row in rows:
                                    if isinstance(row, dict):
                                        if "clause_title" in row:
                                            citations.append(f"Altostrat Singapore Handbook, {row['clause_title']}")
                                        elif "title" in row:
                                            citations.append(f"Altostrat Singapore Handbook, {row['title']}")
                                        
                                        # Check for page indicators in row
                                        for page_key in ("page", "page_number", "page_no", "page_num"):
                                            if page_key in row and row[page_key] is not None:
                                                try:
                                                    detected_pages.add(int(row[page_key]))
                                                except (ValueError, TypeError):
                                                    pass

                final_text = "\n\n".join(extracted_texts) if extracted_texts else str(data)

                # Extract page numbers from text if not found in structured data
                if final_text:
                    page_matches = re.findall(r"(?:Page|page|p\.)\s*:?\s*(\d+)", final_text)
                    for pm in page_matches:
                        try:
                            detected_pages.add(int(pm))
                        except (ValueError, TypeError):
                            pass

                sorted_pages = sorted(list(detected_pages))
                source_doc = build_source_document_link(pages=sorted_pages)

                return {
                    "status": "SUCCESS",
                    "text": final_text,
                    "citations": citations,
                    "pages": sorted_pages,
                    "source_document": source_doc,
                    "sql_queries": sql_queries,
                    "raw_response": data,
                    "source": "BigQuery Conversational API",
                }

            return {
                "status": "API_ERROR",
                "status_code": resp.status_code,
                "error": resp.text,
                "source": "BigQuery Conversational API",
            }

    except Exception as e:
        logger.error(f"Error invoking BigQuery Conversational API: {e}")
        return {
            "status": "EXCEPTION",
            "error": str(e),
            "source": "BigQuery Conversational API",
        }

