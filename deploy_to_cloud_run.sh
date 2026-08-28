#!/bin/bash
set -e

PROJECT_ID="elevate-taiwan-cohort-2"
REGION="us-central1"
REPO_NAME="elevate-repo"
SERVICE_NAME="elevate-multi-agent-app"
IMAGE_TAG="v1.0.0"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/multi-agent:${IMAGE_TAG}"
SA_NAME="sa-elevate-agent"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==================================================================="
echo " Deploying Elevate Multi-Agent Portal to Google Cloud Run"
echo " Project:         $PROJECT_ID"
echo " Region:          $REGION"
echo " Image:           $IMAGE_URI"
echo " Service Name:    $SERVICE_NAME"
echo " Model:           gemini-3.7-flash"
echo " Public Access:   Internet (allow-unauthenticated)"
echo "==================================================================="

# 1. Enable Required GCP APIs
echo "[*] Enabling required APIs (Cloud Run, Artifact Registry, Cloud Build, Vertex AI)..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  --project="$PROJECT_ID"

# 2. Ensure Artifact Registry repository exists
echo "[*] Checking Artifact Registry repository '$REPO_NAME'..."
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "[*] Creating Artifact Registry repository '$REPO_NAME'..."
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Elevate Multi-Agent Docker Repository" \
    --project="$PROJECT_ID"
else
  echo "[✓] Artifact Registry repository '$REPO_NAME' already exists."
fi

# 3. Configure Runtime Service Account & Vertex AI IAM
echo "[*] Checking Service Account '$SA_NAME'..."
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "[*] Creating Service Account '$SA_NAME'..."
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Elevate Multi-Agent Runtime SA" \
    --project="$PROJECT_ID"
else
  echo "[✓] Service Account '$SA_NAME' exists."
fi

echo "[*] Ensuring IAM Vertex AI User permission on '$SA_EMAIL'..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null 2>&1 || true

# 4. Build and Push Container Image via Cloud Build
echo "[*] Submitting Cloud Build container build..."
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcloud builds submit "$DIR" \
  --tag="$IMAGE_URI" \
  --project="$PROJECT_ID"

# 5. Deploy to Cloud Run (Public Internet Access)
echo "[*] Deploying to Cloud Run with public Internet access..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="$SA_EMAIL" \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},MODEL_NAME=gemini-3.7-flash,GOOGLE_API_USE_CLIENT_CERTIFICATE=false,GOOGLE_API_USE_MTLS_ENDPOINT=never" \
  --project="$PROJECT_ID"

echo ""
echo "==================================================================="
echo " Deployment Complete!"
echo " Public Service URL: $(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "==================================================================="
