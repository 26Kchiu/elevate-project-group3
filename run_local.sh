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
echo " Starting Elevate Multi-Agent Portal on port $PORT"
echo " GCP Project:            $GOOGLE_CLOUD_PROJECT"
echo " Model:                  $MODEL_NAME"
echo " WorkWeek MCP:           https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/"
echo " ServiceImmediately MCP: https://mock-saas.aishprabhat.demo.altostrat.com/service-immediately/mcp/"
echo " Web Portal URL:         http://localhost:$PORT"
echo "==================================================================="

if [ -f "$HOME/.local/share/uv/tools/google-adk/bin/uvicorn" ]; then
    "$HOME/.local/share/uv/tools/google-adk/bin/uvicorn" src.app:app --host 0.0.0.0 --port "$PORT" --reload
elif command -v uv &> /dev/null; then
    uv run uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
elif [ -f "$DIR/../.venv/bin/uvicorn" ]; then
    "$DIR/../.venv/bin/uvicorn" src.app:app --host 0.0.0.0 --port "$PORT" --reload
elif [ -f "$DIR/.venv/bin/uvicorn" ]; then
    "$DIR/.venv/bin/uvicorn" src.app:app --host 0.0.0.0 --port "$PORT" --reload
elif command -v uvicorn &> /dev/null; then
    uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
else
    python3 -m uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
fi
