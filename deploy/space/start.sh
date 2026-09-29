#!/bin/sh
# Starts all three processes this Space needs in one container: Redis (the broker), the
# Celery worker (runs the verification pipeline + OCR jobs), then uvicorn in the foreground
# (its exit is what HF Spaces watches, so it must be last and unbackgrounded).
set -e

redis-server --daemonize yes --dir /tmp/redis --save "" --appendonly no
until redis-cli ping >/dev/null 2>&1; do sleep 0.5; done
echo "redis ready"

# Idempotent: only applies revisions not already on the target database (Supabase already has
# the Phase 0 schema from local development, so this is normally a no-op).
python -m alembic upgrade head
echo "schema up to date"

celery -A app.celery_app.celery_app worker --loglevel=info &
echo "celery worker started"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
