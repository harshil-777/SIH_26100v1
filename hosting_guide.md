# Hosting guide

Everything you need to put the GeM Bid Compliance Platform online, for free (backend needs a
card on file for Google Cloud Run, but won't charge at this traffic level).

## What you're deploying

| Piece | Platform | Cost |
|---|---|---|
| Frontend (`web/`) | Vercel | Free |
| API + ML models | Google Cloud Run | Free at this traffic level, needs a card on file |
| Database | Supabase | Free (already set up and seeded) |

Three trained ML models (document field extraction, bid risk scoring, recommendation writing)
assist the rule-based compliance engine, which stays the source of truth for every score and
verdict. They're already published and public on Hugging Face, so the backend can download them
on its own — but see "Model weights" below for a faster/more self-contained option.

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
`trained_models.zip`, right next to this file. The deploy script (step 3) will notice it
automatically and bake the weights straight into the Cloud Run image at deploy time — no
separate file host, no Hugging Face account needed, no dependency on Hugging Face being
reachable when the service starts. It just makes the image ~500 MB bigger and the first deploy a
bit slower to upload.

Either way works identically once deployed — this only affects where the weights come from.

## 2. One-time Google Cloud setup

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

## 3. Deploy the backend

From the repo root, on the `ml-model` branch, with `.env` present (the script reads
`DATABASE_URL` from it — never pass it as a command-line argument, it would land in shell
history):

```bash
./deploy/deploy_cloudrun.sh
```

No local Docker needed — `gcloud run deploy --source` uploads the source and builds the
container server-side via Cloud Build. Takes a few minutes the first time (installing torch +
transformers, longer still if baking in `trained_models.zip`). Early in the output it prints
which model-weights path it took:

```
Found trained_models.zip -- baking model weights into the image (no Hugging Face download at startup) ...
```
or
```
trained_models.zip not found at repo root -- models will be downloaded from Hugging Face on first startup instead.
```

When it finishes, it prints the service URL:

```
https://gem-compliance-api-<random>.<region>.run.app
```

Check it:
```bash
curl https://<your-url>/health      # {"status":"ok"}
curl https://<your-url>/tenders     # real tender data
curl -X POST https://<your-url>/bids/BID-B001-T2026-0001/verify
```

The verify call should come back within a few seconds with `"status":"success"` and a full
result inline — no polling needed, the pipeline runs synchronously on Cloud Run by design (see
"Why no background worker" below).

## 4. Deploy the frontend to Vercel

1. https://vercel.com/new → import the GitHub repo, branch `ml-model`.
2. **Root Directory**: `web` — the one setting that actually matters.
3. **Environment Variables**: `VITE_API_BASE_URL` = your Cloud Run URL from step 3 (no trailing
   slash).
4. Deploy.

`web/vercel.json` already configures the build. No routing config needed — the app uses
hash-based URLs (`#/tenders/...`), which never touch the server.

## 5. Verify it all works

Open the Vercel URL. You should see the tender list, live from Supabase via Cloud Run. Click
into a tender, then a bidder, to see the full detail page (score, documents, audit log, AI
recommendation), and try "Run verification" on a bid. It'll take a few seconds longer than a
local run would (whole pipeline running inline per request, plus a cold start if the service had
scaled to zero) but should complete and show a result with no manual refresh needed.

## Why no background worker (Celery/Redis)

Locally this app uses Celery + Redis to run verification jobs in the background. That's
deliberately **not** used on Cloud Run: Cloud Run throttles a container's CPU to near-zero
*between* requests unless you pay extra for "always allocated" CPU, which would starve a
background worker sitting idle waiting on a queue — it would just never get CPU to check for
work. Instead, the Cloud Run image sets `SYNC_PIPELINE=true`, which makes `/verify` run the whole
compliance pipeline inline within the HTTP request instead of queuing it. A few extra seconds of
response time, correct behavior on this kind of platform.

## Things that are normal, not bugs

- **Cold start**: Cloud Run scales to zero when idle. The first request after a quiet period
  takes longer (loading the ML models — from the image directly if you used
  `trained_models.zip`, otherwise from Hugging Face). Subsequent requests are fast until it
  scales down again.
- **`/verify` takes a few seconds**: expected, see above — it runs the full pipeline inline.
- **Supabase pauses after 7 days idle** (free tier). One request from the Supabase dashboard
  wakes it back up if that happens.
- **Uploaded documents don't persist** across restarts/redeploys — both Cloud Run and the
  container's local disk are ephemeral. Fine for a demo; making it durable means swapping
  `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible store, which isn't
  done here.

## Redeploying later

- Backend: `./deploy/deploy_cloudrun.sh` again.
- Frontend: push to GitHub — Vercel redeploys automatically if connected via the dashboard.

## If something breaks

Cloud Build's build log (linked from the `gcloud run deploy` output, or in the GCP Console under
Cloud Build → History) is the first place to check if the deploy itself fails. If the service
deploys but errors at runtime, `gcloud run services logs read gem-compliance-api --region
YOUR_REGION` shows the container's logs.

There's a second option for the backend, a Hugging Face Space with the Docker SDK
(`deploy/space/`, covered in `deploy/DEPLOY.md`) — it bundles Celery + Redis in one container and
needs no code differences from local dev, but **creating** a Docker Space requires Hugging Face
PRO ($9/mo). Only use it if you already have PRO; Cloud Run above is the free path.
