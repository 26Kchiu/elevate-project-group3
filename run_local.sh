#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"
export PORT="${PORT:-8080}"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-elevate-taiwan-cohort-2}"
export MODEL_NAME="${MODEL_NAME:-gemini-3.7-flash}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_MTLS_ENDPOINT=never

echo "==================================================================="
echo " Starting Elevate Multi-Agent Portal (HCM & ITSM) on port $PORT"
echo " GCP Project:            $GOOGLE_CLOUD_PROJECT"
echo " Model:                  $MODEL_NAME"
echo " WorkWeek MCP:           https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/"
echo " ServiceImmediately MCP: https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/"
echo " Web Portal URL:         http://localhost:$PORT"
echo "==================================================================="

uv run uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
