# Hosting guide

Everything you need to put the GeM Bid Compliance Platform online.

## What you're deploying

| Piece | Platform | Cost |
|---|---|---|
| Frontend (`web/`) | Vercel | Free |
| API + ML models | Railway | No card to start ($5 trial credit); ~$5/month after it runs out |
| Database | Supabase | Free (already set up and seeded) |

Three trained ML models (document field extraction, bid risk scoring, recommendation writing)
assist the rule-based compliance engine, which stays the source of truth for every score and
verdict. They're already published and public on Hugging Face, so the backend can download them
on its own — but see "Model weights" below for a faster/more self-contained option.

There are two backend deploy scripts, covered as two options below. Use whichever fits:

- **Railway** — no card needed to get started, straightforward CLI. The trial credit
  (~$5) covers roughly days-to-weeks of continuous uptime; after that it's Railway's Hobby plan
  at $5/month flat. Good default if you don't want to hand over card details right now.
- **Google Cloud Run** — needs a card on file up front (for identity verification), but is
  genuinely $0/month at this traffic level indefinitely, no recurring charge expected. Good if
  you're OK giving a card but want to actually not pay anything.

Both scripts bake the model weights straight into the deployed image (see "Model weights"
below) — no separate ML hosting service either way.

## 0. Get the code

```bash
git clone https://github.com/harshil-777/SIH_26100v1.git
cd SIH_26100v1
git checkout ml-model
```

You'll also need:
- A copy of `.env` (ask for this directly — has database credentials, don't commit it)
- `trained_models.zip` (~510 MB) — optional but recommended, see below. Too big for git/GitHub
  (100 MB limit), so it has to reach you separately (Drive link, USB, etc).

## 1. Model weights — two options

**Option A (simplest): do nothing.** The deploy script downloads the three trained models from
Hugging Face automatically the first time the backend starts. No extra steps.

**Option B (recommended): use `trained_models.zip`.** Put it at the **repo root**, named exactly
`trained_models.zip`, right next to this file. Either deploy script (Railway or Cloud Run) will
notice it automatically and bake the weights straight into the deployed image — no separate file
host, no Hugging Face account needed, no dependency on Hugging Face being reachable when the
service starts. It just makes the image ~500 MB bigger and the first deploy a bit slower.

Either way works identically once deployed — this only affects where the weights come from.

## 2A. Deploy the backend — Railway (no card to start)

**One-time setup:**
```bash
npm install -g @railway/cli      # or: curl -fsSL https://railway.app/install.sh | sh
railway login                     # opens a browser to sign in
mkdir -p deploy/railway/_build
cd deploy/railway/_build
railway init                      # creates a new Railway project, links this folder to it
cd ../../..                       # back to the repo root
```

**Deploy:**
```bash
./deploy/deploy_railway.sh
```

This assembles the runtime files into `deploy/railway/_build/` (that folder stays linked to your
Railway project across runs — re-running the script always redeploys the same service) and runs
`railway up`. It prints which model-weights path it took, same messages as described above.

**First time only**, give the service a public URL:
```bash
cd deploy/railway/_build && railway domain
```
This prints your live URL, e.g. `https://gem-compliance-api.up.railway.app` — that's what you'll
use as `VITE_API_BASE_URL` in step 3.

**Redeploying later:** just run `./deploy/deploy_railway.sh` again.

## 2B. Deploy the backend — Google Cloud Run (needs a card, but free)

**One-time setup:**
1. Create a GCP project (or use an existing one) at https://console.cloud.google.com. It asks
   for a card on file — Cloud Run's free tier is generous at low traffic, but keep an eye on the
   billing dashboard for the first few days.
2. Install the `gcloud` CLI: https://cloud.google.com/sdk/docs/install
3. Run:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

**Deploy:**
```bash
./deploy/deploy_cloudrun.sh
```

No local Docker needed — `gcloud run deploy --source` uploads the source and builds the
container server-side via Cloud Build. Takes a few minutes the first time (installing torch +
transformers, longer still if baking in `trained_models.zip`). When it finishes, it prints the
service URL:
```
https://gem-compliance-api-<random>.<region>.run.app
```
That's what you'll use as `VITE_API_BASE_URL` in step 3.

**Redeploying later:** just run `./deploy/deploy_cloudrun.sh` again.

## 2C. Check the backend, either option

```bash
curl https://<your-url>/health      # {"status":"ok"}
curl https://<your-url>/tenders     # real tender data
curl -X POST https://<your-url>/bids/BID-B001-T2026-0001/verify
```

The verify call should come back within a few seconds with `"status":"success"` and a full
result inline — no polling needed, the pipeline runs synchronously by design (see "Why no
background worker" below).

## 3. Deploy the frontend to Vercel

1. https://vercel.com/new → import the GitHub repo, branch `ml-model`.
2. **Root Directory**: `web` — the one setting that actually matters.
3. **Environment Variables**: `VITE_API_BASE_URL` = your backend URL from step 2A or 2B (no
   trailing slash).
4. Deploy.

`web/vercel.json` already configures the build. No routing config needed — the app uses
hash-based URLs (`#/tenders/...`), which never touch the server.

## 4. Verify it all works

Open the Vercel URL. You should see the tender list, live from Supabase via your backend. Click
into a tender, then a bidder, to see the full detail page (score, documents, audit log, AI
recommendation), and try "Run verification" on a bid. It'll take a few seconds longer than a
local run would (whole pipeline running inline per request, plus a cold start if the service had
scaled to zero/gone idle) but should complete and show a result with no manual refresh needed.

## Why no background worker (Celery/Redis)

Locally this app uses Celery + Redis to run verification jobs in the background. Neither deploy
option uses that: Cloud Run throttles a container's CPU to near-zero *between* requests unless
you pay extra for "always allocated" CPU, which would starve a background worker sitting idle
waiting on a queue. Railway doesn't have that specific throttling, but running a second
always-on worker service would burn through the trial credit faster for no real benefit here.
Both deploy scripts set `SYNC_PIPELINE=true` instead, which makes `/verify` run the whole
compliance pipeline inline within the HTTP request — a few extra seconds of response time, in
exchange for one simple always-correct backend service on either platform.

## Things that are normal, not bugs

- **Cold start / idle spin-down**: both platforms can go idle and take a bit longer on the first
  request after a quiet period (loading the ML models — from the image directly if you used
  `trained_models.zip`, otherwise from Hugging Face). Subsequent requests are fast.
- **`/verify` takes a few seconds**: expected, see above — it runs the full pipeline inline.
- **Supabase pauses after 7 days idle** (free tier). One request from the Supabase dashboard
  wakes it back up if that happens.
- **Uploaded documents don't persist** across restarts/redeploys — both platforms give the
  container ephemeral local disk. Fine for a demo. Making it durable means swapping
  `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible store, which isn't
  done here.

## If something breaks

**Railway**: `cd deploy/railway/_build && railway logs` shows build and runtime logs. If
`railway up` fails to find a linked project, redo the one-time `railway init` step above.

**Cloud Run**: Cloud Build's build log (linked from the `gcloud run deploy` output, or in the
GCP Console under Cloud Build → History) is the first place to check if the deploy itself fails.
At runtime, `gcloud run services logs read gem-compliance-api --region YOUR_REGION` shows the
container's logs.

There's also a third option for the backend, a Hugging Face Space with the Docker SDK
(`deploy/space/`, covered in `deploy/DEPLOY.md`) — it bundles Celery + Redis in one container and
needs no code differences from local dev, but **creating** a Docker Space requires Hugging Face
PRO ($9/mo). Only worth it if you already have PRO.
