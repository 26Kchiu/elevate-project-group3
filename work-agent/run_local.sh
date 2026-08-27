#!/bin/bash
set -e

echo "=========================================================="
echo " Starting WorkAgent — WorkWeek HCM Virtual Assistant "
echo "=========================================================="

export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-harry-project-elevate}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_MTLS_ENDPOINT=never

PORT="${PORT:-8080}"
echo "Server listening on http://localhost:${PORT}"
python3 -m uvicorn src.app:app --host 0.0.0.0 --port "${PORT}" --reload
