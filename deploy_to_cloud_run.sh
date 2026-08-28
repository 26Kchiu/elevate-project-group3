#!/bin/bash
set -e

PROJECT_ID="elevate-taiwan-cohort-2"
REGION="us-central1"
REPO_NAME="elevate-repo"
SERVICE_NAME="elevate-multi-agent-app"
IMAGE_TAG="v3.0.0"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/multi-agent:${IMAGE_TAG}"
SA_NAME="sa-elevate-agent"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==================================================================="
echo " Deploying Elevate Tri-Agent Portal to Google Cloud Run"
echo " Project:         $PROJECT_ID"
echo " Region:          $REGION"
echo " Image:           $IMAGE_URI"
echo " Service Name:    $SERVICE_NAME"
echo " Agents:          Policy Agent, WorkWeek HCM, ServiceImmediately"
echo "==================================================================="

# 1. Enable Required GCP APIs
echo "[*] Enabling required APIs (Cloud Run, Artifact Registry, Cloud Build, Vertex AI, BigQuery)..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  geminidataanalytics.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID"

# Retrieve Project Number for Cloud Build IAM bindings
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || echo "1040698382265")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "[*] Project Number: $PROJECT_NUMBER"
echo "[*] Ensuring Storage and Artifact Registry permissions for Cloud Build service accounts..."

# 2. Ensure Cloud Build Storage & Artifact Registry Permissions
for SA in "$COMPUTE_SA" "$CLOUDBUILD_SA"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" \
    --role="roles/storage.objectViewer" \
    --condition=None >/dev/null 2>&1 || true

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" \
    --role="roles/storage.admin" \
    --condition=None >/dev/null 2>&1 || true

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" \
    --role="roles/logging.logWriter" \
    --condition=None >/dev/null 2>&1 || true

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" \
    --role="roles/artifactregistry.writer" \
    --condition=None >/dev/null 2>&1 || true
done

# 3. Ensure Artifact Registry repository exists
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

# 4. Configure Runtime Service Account & IAM
echo "[*] Checking Runtime Service Account '$SA_NAME'..."
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "[*] Creating Service Account '$SA_NAME'..."
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Elevate Multi-Agent Runtime SA" \
    --project="$PROJECT_ID"
else
  echo "[✓] Service Account '$SA_NAME' exists."
fi

echo "[*] Ensuring IAM roles (Vertex AI, BigQuery, Storage) on '$SA_EMAIL'..."
for ROLE in "roles/aiplatform.user" "roles/bigquery.user" "roles/bigquery.dataViewer" "roles/storage.objectViewer"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None >/dev/null 2>&1 || true
done

# 5. Build and Push Container Image via Cloud Build
echo "[*] Submitting Cloud Build container build..."
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcloud builds submit "$DIR" \
  --tag="$IMAGE_URI" \
  --project="$PROJECT_ID"

# 6. Deploy to Cloud Run
echo "[*] Deploying to Cloud Run..."
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
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},MODEL_NAME=auto,BIGQUERY_DATA_AGENT_ID=agent_98c36166-3d31-471e-8fce-4dc446069ad7,BIGQUERY_DATA_AGENT_LOCATION=US,GOOGLE_API_USE_CLIENT_CERTIFICATE=false,GOOGLE_API_USE_MTLS_ENDPOINT=never" \
  --project="$PROJECT_ID"

# 7. Ensure Invoker permissions for domain user
echo "[*] Ensuring Invoker IAM role on '$SERVICE_NAME'..."
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
  --region="$REGION" \
  --member="user:harrylin@gcp.altostrat.com" \
  --role="roles/run.invoker" \
  --project="$PROJECT_ID" >/dev/null 2>&1 || true

echo ""
echo "==================================================================="
echo " Deployment Complete!"
echo " Service Name:        $SERVICE_NAME"
echo " Live Cloud Run URL:  $(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "==================================================================="
