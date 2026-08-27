#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"
export PORT="${PORT:-8080}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_MTLS_ENDPOINT=never

echo "==================================================================="
echo " Starting Elevate Multi-Agent Portal (HCM & ITSM) on port $PORT"
echo " WorkWeek MCP:           https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/"
echo " ServiceImmediately MCP: https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/"
echo " Web Portal URL:         http://localhost:$PORT"
echo "==================================================================="

/usr/local/google/home/harrylin/.venv/bin/uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
