#!/usr/bin/env bash
# Deploys the backend to Railway (https://railway.app) instead of Google Cloud Run.
#
# Why this exists alongside deploy_cloudrun.sh: Railway needs no card on file to start (a $5
# trial credit, no billing details required), and unlike Render/Koyeb's free tier it bills by
# actual usage rather than a fixed ~512MB RAM cap -- which matters here, since the three loaded
# ML models (DistilBERT + flan-t5-small + LightGBM) need roughly 1-1.5GB together. The trade-off:
# the $5 trial runs out in days-to-weeks of continuous uptime, after which it's Railway's Hobby
# plan at $5/month flat. Cloud Run needs a card up front but is genuinely $0/month at this
# traffic level indefinitely -- pick whichever trade-off you'd rather make.
#
# Unlike `gcloud run deploy --source` (which accepts any directory), the Railway CLI links a
# *directory's path* to a project -- so this script reuses one persistent build directory across
# runs (deploy/railway/_build, gitignored) instead of a fresh temp dir each time. A fresh temp
# dir every run would mean a never-before-linked path every time, so `railway up` would have
# nothing to attach to.
#
# Prerequisites (one-time):
#   1. Install the CLI: npm install -g @railway/cli   (or: curl -fsSL https://railway.app/install.sh | sh)
#   2. railway login
#   3. mkdir -p deploy/railway/_build && cd deploy/railway/_build && railway init
#      (creates a new Railway project and links this directory to it -- do this once, then cd
#      back to the repo root)
#
# Usage:
#   ./deploy/deploy_railway.sh
#
# Reads DATABASE_URL from .env in the repo root -- never pass it as a command-line argument,
# which would land in your shell history.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/deploy/railway/_build"

if ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI not found. Install it: npm install -g @railway/cli" >&2
  exit 1
fi

DATABASE_URL="$(grep -E '^DATABASE_URL=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL not found in $REPO_ROOT/.env -- set it there first." >&2
  exit 1
fi

mkdir -p "$BUILD_DIR"

if ! (cd "$BUILD_DIR" && railway status >/dev/null 2>&1); then
  echo "This directory isn't linked to a Railway project yet. One-time setup:" >&2
  echo "  cd $BUILD_DIR && railway login && railway init" >&2
  echo "Then re-run this script from the repo root." >&2
  exit 1
fi

echo "Assembling deployment in $BUILD_DIR ..."
rm -rf "$BUILD_DIR/app" "$BUILD_DIR/ml" "$BUILD_DIR/ml_weights" "$BUILD_DIR/WORKING DOCUMENTS"
cp -r "$REPO_ROOT/app" "$BUILD_DIR/app"
cp "$REPO_ROOT/alembic.ini" "$BUILD_DIR/alembic.ini"
cp "$REPO_ROOT/requirements.txt" "$BUILD_DIR/requirements.txt"
cp -r "$REPO_ROOT/WORKING DOCUMENTS" "$BUILD_DIR/WORKING DOCUMENTS"
cp "$REPO_ROOT/deploy/cloudrun/Dockerfile" "$BUILD_DIR/Dockerfile"

# ml/ inference code (not ml/data or ml/models -- synthetic training data and local training
# output, both huge and gitignored, never needed at inference time).
mkdir -p "$BUILD_DIR/ml"
cp -r "$REPO_ROOT/ml/extraction" "$REPO_ROOT/ml/risk" "$REPO_ROOT/ml/recommendation" "$REPO_ROOT/ml/common" "$BUILD_DIR/ml/"
[ -f "$REPO_ROOT/ml/__init__.py" ] && cp "$REPO_ROOT/ml/__init__.py" "$BUILD_DIR/ml/__init__.py"
find "$BUILD_DIR/app" "$BUILD_DIR/ml" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Model weights: bake trained_models.zip straight into the image if this machine has it, so the
# service never needs Hugging Face reachable at startup. Falls back to the HF download path if
# the zip isn't here.
mkdir -p "$BUILD_DIR/ml_weights"
BAKED_WEIGHTS=false
if [ -f "$REPO_ROOT/trained_models.zip" ]; then
  echo "Found trained_models.zip -- baking model weights into the image (no Hugging Face download at startup) ..."
  UNZIP_TMP="$(mktemp -d)"
  unzip -q "$REPO_ROOT/trained_models.zip" -d "$UNZIP_TMP"
  cp -r "$UNZIP_TMP/models/"* "$BUILD_DIR/ml_weights/"
  rm -rf "$UNZIP_TMP"
  BAKED_WEIGHTS=true
else
  echo "trained_models.zip not found at repo root -- models will be downloaded from Hugging Face on first startup instead."
fi

echo "Setting environment variables ..."
(
  cd "$BUILD_DIR"
  railway variable set "DATABASE_URL=$DATABASE_URL"
  railway variable set "ML_MODELS_ENABLED=true"
  railway variable set "SYNC_PIPELINE=true"
  if [ "$BAKED_WEIGHTS" = true ]; then
    railway variable set "ML_EXTRACTION_MODEL=/app/ml_weights/extraction"
    railway variable set "ML_RISK_MODEL=/app/ml_weights/risk"
    railway variable set "ML_RECOMMENDATION_MODEL=/app/ml_weights/recommendation"
  fi
)

echo "Deploying to Railway ..."
(cd "$BUILD_DIR" && railway up --detach)

echo
echo "Deploy started. First time only -- give the service a public URL:"
echo "  cd $BUILD_DIR && railway domain"
echo "Check build/runtime progress any time: cd $BUILD_DIR && railway logs"
