#!/usr/bin/env bash
# Pushes the backend to a Hugging Face Space, which is its own separate git repo (not this
# GitHub repo). Assembles only what the container needs into a scratch directory -- not the
# whole monorepo -- because a Space's README.md carries its deployment metadata (YAML
# frontmatter) and can't be this project's regular README at the same time.
#
# Usage:
#   1. Create the Space first at https://huggingface.co/new-space (SDK: Docker, any hardware
#      on the free tier), then add your Postgres DATABASE_URL under
#      Settings -> Variables and secrets.
#   2. ./deploy/push_to_space.sh https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
#
# Needs `git` and, since Spaces enforce auth on push, a credential helper or a token pasted at
# the username/password prompt (Settings -> Access Tokens, a `write` token, used as the
# password; the username can be anything).
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <hugging-face-space-git-url>" >&2
  echo "e.g.:  $0 https://huggingface.co/spaces/YOUR_USERNAME/bid-auth" >&2
  exit 1
fi
SPACE_URL="$1"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

echo "Assembling Space deployment in $SCRATCH ..."
cp -r "$REPO_ROOT/app" "$SCRATCH/app"
cp "$REPO_ROOT/alembic.ini" "$SCRATCH/alembic.ini"
cp "$REPO_ROOT/requirements.txt" "$SCRATCH/requirements.txt"
cp -r "$REPO_ROOT/WORKING DOCUMENTS" "$SCRATCH/WORKING DOCUMENTS"
cp "$REPO_ROOT/deploy/space/Dockerfile" "$SCRATCH/Dockerfile"
cp "$REPO_ROOT/deploy/space/start.sh" "$SCRATCH/start.sh"
cp "$REPO_ROOT/deploy/space/README.md" "$SCRATCH/README.md"

# __pycache__ directories from local runs shouldn't ship; everything else in app/ is needed.
find "$SCRATCH/app" -name "__pycache__" -type d -prune -exec rm -rf {} +

cd "$SCRATCH"
git init -q
git add -A
git commit -q -m "Deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git remote add space "$SPACE_URL"
echo "Pushing to $SPACE_URL ..."
git push -f space HEAD:main

echo
echo "Pushed. Build logs: ${SPACE_URL/huggingface.co/huggingface.co}/logs"
echo "Once it's live, the API is at: $(echo "$SPACE_URL" | sed -E 's#https://huggingface.co/spaces/([^/]+)/(.+)#https://\1-\2.hf.space#' | tr '[:upper:]' '[:lower:]')"
