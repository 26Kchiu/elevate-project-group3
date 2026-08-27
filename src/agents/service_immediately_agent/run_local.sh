#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../../.." && pwd)"

export PYTHONPATH="$REPO_ROOT:$PYTHONPATH"
export SERVICE_IMMEDIATELY_MCP_URL="${SERVICE_IMMEDIATELY_MCP_URL:-https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/}"
export SERVICE_IMMEDIATELY_MCP_TOKEN="${SERVICE_IMMEDIATELY_MCP_TOKEN:-mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_MTLS_ENDPOINT=never

echo "================================================================"
echo " Running ServiceImmediately Agent Standalone CLI Test "
echo " MCP Endpoint: $SERVICE_IMMEDIATELY_MCP_URL"
echo " Model: gemini-3.7-flash"
echo "================================================================"

/usr/local/google/home/harrylin/.venv/bin/python -m src.agents.service_immediately_agent.agent
