# Deploying

`hosting_guide.md` at the repo root is the full step-by-step walkthrough written for someone
deploying this cold. This file is the shorter reference on *why* each option is built the way it
is.

## The three backend options

| | Card needed | Cost | Notes |
|---|---|---|---|
| **Railway** (recommended to start) | No | $5 trial credit, then ~$5/month flat | `deploy/deploy_railway.sh` — bills by actual usage, not a fixed RAM cap, so it comfortably fits all 3 ML models loaded at once |
| **Google Cloud Run** | Yes (for verification) | Free at this traffic level indefinitely | `deploy/deploy_cloudrun.sh` — no Docker needed locally, builds server-side |
| **Hugging Face Space (Docker)** | No — needs HF PRO | $9/month subscription | `deploy/push_to_space.sh` — simplest code-wise (Celery+Redis bundled in one container), but gated behind a subscription |

Frontend is Vercel in all three cases (free, no card). Database is Supabase in all three cases
(free, already set up).

Render and Koyeb's free tiers were considered and ruled out: both cap free instances at ~512MB
RAM, and the three loaded models (DistilBERT + flan-t5-small + LightGBM) need roughly 1-1.5GB
together once torch's own overhead is counted — that would OOM on either platform.

---

## Option A: Railway (no card, usage-based billing)

```bash
railway login
mkdir -p deploy/railway/_build && cd deploy/railway/_build && railway init && cd ../../..
./deploy/deploy_railway.sh
```

The Railway CLI links a *directory's path* to a project (not just an account-level config), so
the script keeps one persistent build directory (`deploy/railway/_build/`, gitignored) instead of
a fresh temp dir per run — a fresh path every time would mean nothing to attach the deploy to.

No Celery/Redis here either (see Option B's rationale below — same reasoning applies: keeping one
simple always-on service is worth more than the marginal benefit of a background worker).

## Option B: Google Cloud Run (needs a card, genuinely free)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com   # once

./deploy/deploy_cloudrun.sh
```

No Celery/Redis in this path — `/verify` runs the pipeline inline within the request
(`SYNC_PIPELINE=true`, set automatically by `deploy/cloudrun/Dockerfile`), because Cloud Run
throttles CPU between requests by default and a background worker would starve waiting on a
queue that never gets CPU to check itself.

## Both A and B: model weights

If `trained_models.zip` (see `hosting_guide.md`) is present at the repo root when you run either
deploy script, it bakes the model weights straight into the image so the service never needs
Hugging Face reachable at startup. If it's not there, the service downloads the weights from
Hugging Face on first startup instead — both paths work, the script just picks whichever one it
can.

## Option C: Hugging Face Space (needs PRO, $9/mo)

**Create the Space:**
1. https://huggingface.co/new-space
2. SDK: **Docker**, hardware: CPU basic. (Requires PRO on your account to create.)
3. **Settings → Variables and secrets** → add secret `DATABASE_URL` = your Supabase connection string.

**Push the code:**
```bash
./deploy/push_to_space.sh https://huggingface.co/spaces/YOUR_USERNAME/bid-auth
```
Prompts for git credentials on push — username can be anything, password is an HF **write**
token (Settings → Access Tokens). Pushes only the runtime files (`app/`, `alembic.ini`,
`requirements.txt`, seed data, the Dockerfile) into the Space's own separate git repo as a
fresh single commit each time — not your GitHub history.

Unlike Railway/Cloud Run, this bundles Redis + a real Celery worker in the same always-on
container (HF Spaces doesn't throttle CPU the way Cloud Run does), so `/verify` keeps its
original queue-and-poll behaviour with no code differences from local dev.

Live at `https://YOUR_USERNAME-<space-name>.hf.space` once the build finishes.

---

## Frontend — Vercel (all options)

1. https://vercel.com/new → import the GitHub repo.
2. **Root Directory**: `web`.
3. **Environment Variables**: `VITE_API_BASE_URL` = your backend's URL from whichever option you picked (no trailing slash).
4. Deploy.

`web/vercel.json` already configures the build. No SPA-rewrite config needed — the app uses
hash-based routing (`#/tenders/...`), which never touches the server.

## Verify

Open the Vercel URL: tender list, live from Supabase via your backend. Click through to a
bidder to see the full detail page and try "Run verification".

## Known caveats (all options)

- **Uploaded documents don't persist** across restarts/redeploys — all platforms give the
  container ephemeral local disk. Fine for a demo; fixing it means swapping
  `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible store.
- **Cold starts / idle spin-down**: Railway and Cloud Run can go idle and take longer on the
  first request after a quiet period (reloading the models).

## Redeploying later

- Railway: `./deploy/deploy_railway.sh` again.
- Cloud Run: `./deploy/deploy_cloudrun.sh` again.
- HF Space: `./deploy/push_to_space.sh <space-url>` again.
- Frontend: push to GitHub — Vercel redeploys automatically if connected via the dashboard.
