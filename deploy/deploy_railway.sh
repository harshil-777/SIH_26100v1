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
# Also handles a real gotcha, confirmed against a live deploy: Railway containers have no
# outbound IPv6 by default, but Supabase's direct db.<ref>.supabase.co host is IPv6-only, so
# without the fix below the container crash-loops on every DB connection with "Network is
# unreachable". This script enables IPv6 egress via Railway's GraphQL API on every run (there's
# no plain CLI flag for it) -- no action needed on your part.
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
# The deployed Vercel frontend's origin -- app/main.py's CORS middleware only allows
# http://localhost:5173 by default, so without this the browser blocks every API call from the
# real deployed site. Override with FRONTEND_ORIGIN=... if your Vercel URL differs.
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://bid-auth.vercel.app}"

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

# Model weights: unlike deploy_cloudrun.sh, this deliberately does NOT bake trained_models.zip
# into the upload. Railway's `railway up` goes through an upload gateway capped at 512MiB --
# the zip alone (~510MB) plus app/ml code pushes the total past that limit and the upload is
# rejected outright (confirmed: a real attempt failed with "413 Payload Too Large" at 536705014
# bytes, right at the 512MiB=536870912 boundary). So on Railway the service always downloads the
# three models from Hugging Face on first startup -- ml_weights/ here stays an empty placeholder
# (the Dockerfile COPYs it unconditionally) and ML_EXTRACTION_MODEL etc are left unset so
# app/config.py's HF-repo-id defaults apply.
rm -rf "$BUILD_DIR/ml_weights"
mkdir -p "$BUILD_DIR/ml_weights"

echo "Setting environment variables ..."
(
  cd "$BUILD_DIR"
  railway variable set "DATABASE_URL=$DATABASE_URL"
  railway variable set "ML_MODELS_ENABLED=true"
  railway variable set "SYNC_PIPELINE=true"
  railway variable set "CORS_ORIGINS=$FRONTEND_ORIGIN"
  # Single API process, no Celery worker on this platform (see SYNC_PIPELINE above), so it's
  # safe to keep connections open between requests instead of paying a fresh TLS handshake to
  # Supabase (in Seoul) on every single request -- this was set on the Cloud Run image but had
  # been missed here, leaving Railway on NullPool the whole time.
  railway variable set "DB_POOL_SIZE=5"
  # Clear these in case an earlier run of this script set them before this limitation was found --
  # harmless no-ops if they were never set.
  railway variable delete "ML_EXTRACTION_MODEL" 2>/dev/null || true
  railway variable delete "ML_RISK_MODEL" 2>/dev/null || true
  railway variable delete "ML_RECOMMENDATION_MODEL" 2>/dev/null || true
)

# Railway containers have no outbound IPv6 by default, but Supabase's direct db.<ref>.supabase.co
# host is IPv6-only -- without this, alembic's migration step (and every DB connection after it)
# fails with "OSError: [Errno 101] Network is unreachable" and the deploy crash-loops. There's no
# plain CLI flag for this, so it goes through Railway's GraphQL API directly. Confirmed this is
# read on each new deploy (not just once at container boot), so setting it before every `railway
# up` is redundant-but-harmless rather than strictly one-time.
SERVICE_ID="$(cd "$BUILD_DIR" && railway service list --json 2>/dev/null | grep -m1 '"id"' | sed -E 's/.*"id": *"([^"]+)".*/\1/')"
if [ -n "$SERVICE_ID" ]; then
  (cd "$BUILD_DIR" && railway api \
    'mutation($serviceId: String!, $input: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(serviceId: $serviceId, input: $input) }' \
    --var "serviceId=$SERVICE_ID" \
    --var 'input={"ipv6EgressEnabled": true}' >/dev/null 2>&1) \
    && echo "IPv6 egress enabled (needed for Supabase's direct connection host)." \
    || echo "Warning: could not confirm IPv6 egress setting -- if the deploy crash-loops on DB connect, this is why." >&2
fi

echo "Deploying to Railway ..."
(cd "$BUILD_DIR" && railway up --detach)

echo
echo "Deploy started. First time only -- give the service a public URL:"
echo "  cd $BUILD_DIR && railway domain"
echo "Check build/runtime progress any time: cd $BUILD_DIR && railway logs"
