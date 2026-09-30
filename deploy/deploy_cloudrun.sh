#!/usr/bin/env bash
# Deploys the backend to Google Cloud Run.
#
# Unlike the Hugging Face Space path, this doesn't need a local Docker build: `gcloud run
# deploy --source` uploads the source and builds it server-side via Cloud Build, so it works
# from a machine without Docker too.
#
# Prerequisites (one-time):
#   1. A GCP project with billing enabled (Cloud Run's free tier needs a card on file, but
#      won't charge at low traffic -- see hosting_guide.md).
#   2. gcloud CLI installed and authenticated: https://cloud.google.com/sdk/docs/install
#      then: gcloud auth login && gcloud config set project YOUR_PROJECT_ID
#   3. Enable the needed APIs once: gcloud services enable run.googleapis.com cloudbuild.googleapis.com
#
# Usage:
#   ./deploy/deploy_cloudrun.sh [service-name] [region]
#   (defaults: gem-compliance-api, us-central1)
#
# Reads DATABASE_URL from .env in the repo root -- never pass it as a command-line argument,
# which would land in your shell history.
set -euo pipefail

SERVICE_NAME="${1:-bid-auth}"
REGION="${2:-us-central1}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The deployed Vercel frontend's origin -- app/main.py's CORS middleware only allows
# http://localhost:5173 by default, so without this the browser blocks every API call from the
# real deployed site. Override with FRONTEND_ORIGIN=... if your Vercel URL differs.
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://bid-auth.vercel.app}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI not found. Install it: https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi

DATABASE_URL="$(grep -E '^DATABASE_URL=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL not found in $REPO_ROOT/.env -- set it there first." >&2
  exit 1
fi

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

echo "Assembling deployment in $SCRATCH ..."
cp -r "$REPO_ROOT/app" "$SCRATCH/app"
cp "$REPO_ROOT/alembic.ini" "$SCRATCH/alembic.ini"
cp "$REPO_ROOT/requirements.txt" "$SCRATCH/requirements.txt"
cp -r "$REPO_ROOT/WORKING DOCUMENTS" "$SCRATCH/WORKING DOCUMENTS"
cp "$REPO_ROOT/deploy/cloudrun/Dockerfile" "$SCRATCH/Dockerfile"

# ml/ inference code (not ml/data or ml/models -- synthetic training data and local training
# output, both huge and gitignored, never needed at inference time).
mkdir -p "$SCRATCH/ml"
cp -r "$REPO_ROOT/ml/extraction" "$REPO_ROOT/ml/risk" "$REPO_ROOT/ml/recommendation" "$REPO_ROOT/ml/common" "$SCRATCH/ml/"
[ -f "$REPO_ROOT/ml/__init__.py" ] && cp "$REPO_ROOT/ml/__init__.py" "$SCRATCH/ml/__init__.py"
find "$SCRATCH/app" "$SCRATCH/ml" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Model weights: bake trained_models.zip straight into the image if this machine has it, so the
# service never needs Hugging Face reachable at startup. Falls back to the HF download path
# (unchanged from before) if the zip isn't here -- e.g. a machine that only cloned the git repo.
mkdir -p "$SCRATCH/ml_weights"
BAKED_WEIGHTS=false
if [ -f "$REPO_ROOT/trained_models.zip" ]; then
  echo "Found trained_models.zip -- baking model weights into the image (no Hugging Face download at startup) ..."
  UNZIP_TMP="$(mktemp -d)"
  unzip -q "$REPO_ROOT/trained_models.zip" -d "$UNZIP_TMP"
  cp -r "$UNZIP_TMP/models/"* "$SCRATCH/ml_weights/"
  rm -rf "$UNZIP_TMP"
  BAKED_WEIGHTS=true
else
  echo "trained_models.zip not found at repo root -- models will be downloaded from Hugging Face on first startup instead."
fi

ENV_VARS="DATABASE_URL=$DATABASE_URL,CORS_ORIGINS=$FRONTEND_ORIGIN"
if [ "$BAKED_WEIGHTS" = true ]; then
  ENV_VARS="$ENV_VARS,ML_EXTRACTION_MODEL=/app/ml_weights/extraction,ML_RISK_MODEL=/app/ml_weights/risk,ML_RECOMMENDATION_MODEL=/app/ml_weights/recommendation"
fi

echo "Deploying $SERVICE_NAME to Cloud Run ($REGION) ..."
gcloud run deploy "$SERVICE_NAME" \
  --source "$SCRATCH" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "$ENV_VARS"

URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')"
echo
echo "Deployed: $URL"
echo "Check:    curl $URL/health"
