# Google Cloud Run deployment: API only, no Redis/Celery worker (see app/config.py's
# sync_pipeline -- Cloud Run throttles CPU between requests by default, which would starve a
# background worker idling on a queue, so /verify runs the pipeline inline instead).
#
# Built and pushed by deploy/deploy_cloudrun.sh, which also sets SYNC_PIPELINE=true and the
# other required env vars/secrets on the Cloud Run service. Untested against a real `gcloud`
# deploy (no GCP project available on the machine that wrote this) -- Cloud Build's own build
# log and the service's first request are the real tests.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU wheel: the plain `pip install torch` default pulls CUDA wheels, unnecessary here and
# far larger than needed.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY app ./app
COPY "WORKING DOCUMENTS" "./WORKING DOCUMENTS"
RUN mkdir -p /app/storage

ENV ML_MODELS_ENABLED=true \
    SYNC_PIPELINE=true

# Cloud Run injects $PORT (8080 by default) and expects the container to listen on it, not on
# a fixed port -- the shell form of CMD lets $PORT expand at container start.
CMD python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
