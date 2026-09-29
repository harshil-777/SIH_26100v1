# Hugging Face Space (Docker SDK): API + Celery worker + Redis in one free CPU container.
# Not used for local dev -- that's the repo-root Dockerfile + docker-compose.yml. This one is
# pushed to a Space's own git repo by deploy/push_to_space.sh, which copies it in as
# "Dockerfile" alongside app/, alembic.ini, requirements.txt and this folder's start.sh.
#
# Untested against a real Docker daemon (none available on the machine that wrote this) --
# HF Spaces builds server-side, so its build log is the first real test. If it fails there,
# the traceback is usually enough to fix inline; nothing here is exotic.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential tesseract-ocr redis-server \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces run the container as uid 1000 with no home directory by default; huggingface_hub
# and pip both want a writable HOME (model cache, --user installs), so create one up front.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

COPY --chown=user requirements.txt .
# CPU wheel: the plain `pip install torch` default would try to pull CUDA wheels, which are
# both unnecessary and far larger than this free tier's disk budget.
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user alembic.ini .
COPY --chown=user app ./app
COPY --chown=user "WORKING DOCUMENTS" "./WORKING DOCUMENTS"
COPY --chown=user start.sh .
RUN chmod +x start.sh && mkdir -p /app/storage /tmp/redis

# ML_MODELS_ENABLED and the ML_*_MODEL repo ids are already the defaults in app/config.py;
# only DATABASE_URL is genuinely secret -- set that (and REDIS_URL if it ever changes) in the
# Space's Settings -> Variables and secrets, not here.
ENV ML_MODELS_ENABLED=true \
    REDIS_URL=redis://localhost:6379/0

USER user
EXPOSE 7860
CMD ["./start.sh"]
