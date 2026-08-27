#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../../.." && pwd)"

export PYTHONPATH="$REPO_ROOT:$PYTHONPATH"
export WORKWEEK_MCP_URL="${WORKWEEK_MCP_URL:-https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/}"
export WORKWEEK_MCP_TOKEN="${WORKWEEK_MCP_TOKEN:-mcp__odawPH3AEWphSkF7ZK-i2vQMUfhI7FtcXBvQAF80Jg}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_MTLS_ENDPOINT=never
export PORT="${PORT:-8080}"

echo "========================================================"
echo " Starting WorkWeek HCM Agent Local Web GUI & API Server "
echo " MCP Endpoint: $WORKWEEK_MCP_URL"
echo " Web GUI URL:  http://localhost:$PORT"
echo "========================================================"

/usr/local/google/home/harrylin/.venv/bin/uvicorn src.agents.workweek_hcm_agent.app:app --host 0.0.0.0 --port "$PORT" --reload
