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

SERVICE_NAME="${1:-gem-compliance-api}"
REGION="${2:-us-central1}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
find "$SCRATCH/app" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "Deploying $SERVICE_NAME to Cloud Run ($REGION) ..."
gcloud run deploy "$SERVICE_NAME" \
  --source "$SCRATCH" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "DATABASE_URL=$DATABASE_URL"

URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')"
echo
echo "Deployed: $URL"
echo "Check:    curl $URL/health"
