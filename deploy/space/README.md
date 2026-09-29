---
title: GeM Bid Compliance API
emoji: 📋
colorFrom: emerald
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# GeM Bid Compliance API

FastAPI backend for the GeM Bid Compliance platform: verification pipeline, rule engine, and
three trained models loaded from Hugging Face at startup
([extraction](https://huggingface.co/HarshilDaGoat/gem-certificate-extractor),
[risk](https://huggingface.co/HarshilDaGoat/gem-bid-risk),
[recommendation](https://huggingface.co/HarshilDaGoat/gem-recommendation-writer)).

This Space is the API only. The dashboard lives separately on Vercel and talks to this Space's
URL (`https://<space>.hf.space`) over HTTPS.

Source: https://github.com/harshil-777/SIH_26100v1 (this Space is a deployment target, pushed
by `deploy/push_to_space.sh` from the `ml-model` branch -- not developed here directly).

**Required Space secret:** `DATABASE_URL` (Settings → Variables and secrets), pointing at your
Postgres. Everything else has a working default (see `app/config.py`).

**Known limitation:** uploaded documents are stored on the container's local disk
(`STORAGE_DIR`), which HF Spaces does not persist across restarts. Fine for a demo; for
anything longer-lived, point `ObjectStore` (`app/services/object_store.py`) at S3-compatible
storage instead.
