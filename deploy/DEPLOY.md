# Deploying for free

> **Correction**: this originally recommended a Hugging Face Space (Docker SDK) for the
> backend. That was wrong — creating a Docker or Gradio Space requires HF PRO ($9/mo); only
> Static Spaces and the CPU-Basic *hardware itself* (once you have access) are free. See
> `hosting_guide.md` for the full correction and current recommendation (Google Cloud Run).
> The `deploy/space/` files below still work correctly if you do have PRO.

## The two backend options

| | Free without a card | Needs a card on file | Notes |
|---|---|---|---|
| **Google Cloud Run** (recommended) | No | Yes (won't charge at low traffic) | `deploy/deploy_cloudrun.sh` — no Docker needed locally, builds server-side |
| **Hugging Face Space (Docker)** | No — needs HF PRO | No | `deploy/push_to_space.sh` — simpler (Celery+Redis bundled in one container), but gated behind a subscription |

Frontend is Vercel either way (free, no card). Database is Supabase either way (free, already
set up).

---

## Option A: Google Cloud Run (no HF PRO needed)

Full walkthrough: **`hosting_guide.md`** at the repo root. Short version:

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

## Option B: Hugging Face Space (needs PRO, $9/mo)

**Create the Space:**
1. https://huggingface.co/new-space
2. SDK: **Docker**, hardware: CPU basic. (Requires PRO on your account to create.)
3. **Settings → Variables and secrets** → add secret `DATABASE_URL` = your Supabase connection string.

**Push the code:**
```bash
./deploy/push_to_space.sh https://huggingface.co/spaces/YOUR_USERNAME/gem-compliance-api
```
Prompts for git credentials on push — username can be anything, password is an HF **write**
token (Settings → Access Tokens). Pushes only the runtime files (`app/`, `alembic.ini`,
`requirements.txt`, seed data, the Dockerfile) into the Space's own separate git repo as a
fresh single commit each time — not your GitHub history.

Unlike Cloud Run, this bundles Redis + a real Celery worker in the same always-on container
(HF Spaces doesn't throttle CPU the way Cloud Run does), so `/verify` keeps its original
queue-and-poll behaviour with no code differences from local dev.

Live at `https://YOUR_USERNAME-<space-name>.hf.space` once the build finishes.

---

## Frontend — Vercel (either option)

1. https://vercel.com/new → import the GitHub repo.
2. **Root Directory**: `web`.
3. **Environment Variables**: `VITE_API_BASE_URL` = your backend's URL from whichever option you picked (no trailing slash).
4. Deploy.

`web/vercel.json` already configures the build. No SPA-rewrite config needed — the app uses
hash-based routing (`#/tenders/...`), which never touches the server.

## Verify

Open the Vercel URL: tender list, live from Supabase via your backend. Click through to a
bidder to see the full detail page and try "Run verification".

## Known caveats (both options)

- **Uploaded documents don't persist** across restarts/redeploys — both platforms give the
  container ephemeral local disk. Fine for a demo; fixing it means swapping
  `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible store.
- **Cold starts**: both platforms scale to zero when idle and take longer on the first request
  after a quiet period (reloading the models).

## Redeploying later

- Cloud Run: `./deploy/deploy_cloudrun.sh` again.
- HF Space: `./deploy/push_to_space.sh <space-url>` again.
- Frontend: push to GitHub — Vercel redeploys automatically if connected via the dashboard.
