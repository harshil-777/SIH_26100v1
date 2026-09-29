# Hosting guide

Everything needed to put this online for free.

## Correction from an earlier version of this file

This file originally said to run the backend on a Hugging Face Space (Docker SDK) for free.
That was wrong: Hugging Face's own docs are explicit that **creating** a Docker or Gradio Space
requires a paid PRO plan, even though the CPU-Basic hardware itself has no hourly cost once
you have access. Static Spaces are free; Docker Spaces are not. (Verified directly against
[huggingface.co/docs/hub/en/spaces-overview](https://huggingface.co/docs/hub/en/spaces-overview),
September 2026.)

The backend now deploys to **Google Cloud Run** instead (see below). The `deploy/space/`
files (Dockerfile, start.sh, push script) still exist and still work correctly — they're just
not free to use unless you have HF PRO. If you do have PRO, they're still the simpler path
(everything in one container, no code changes) and `deploy/DEPLOY.md` covers them.

## What's already done

- Branch: `ml-model`. Pull it: `git checkout ml-model && git pull`
- Three trained models are already public on Hugging Face and need no further action:
  [extraction](https://huggingface.co/HarshilDaGoat/gem-certificate-extractor),
  [risk](https://huggingface.co/HarshilDaGoat/gem-bid-risk),
  [recommendation](https://huggingface.co/HarshilDaGoat/gem-recommendation-writer). Downloading
  models from the Hub is always free — only *running compute in a Space* is gated. The backend
  downloads them at startup regardless of where it's hosted.
- Database: Supabase, already set up and seeded. You'll just need the `DATABASE_URL`.

## Model weights, without depending on Hugging Face at all

`trained_models.zip` (~510 MB) is a plain copy of the same three trained models, zipped up. It's
**not in git** — GitHub rejects files over 100 MB and this is way past that — so it has to reach
you some other way (Drive link, USB, etc. — whoever has it will send it directly).

You don't strictly need it. If it's missing, `deploy_cloudrun.sh` just deploys the way it did
before: the service downloads the same weights from Hugging Face the first time it starts. But if
you *have* the zip, put it at the **repo root** (next to `hosting_guide.md`, named exactly
`trained_models.zip`) before running the deploy script — it will notice it automatically and bake
the weights straight into the Cloud Run image at deploy time. No separate file host, no extra
account, no code changes: the model files just travel inside the same container build that
already ships `app/`.

What this buys you: the deployed service never has to reach Hugging Face at all, at startup or
otherwise — one less external dependency and no first-request download delay. The image is
correspondingly ~500 MB bigger and takes a bit longer to push to Cloud Build the first time.

(For local/dev runs instead of Cloud Run, the same zip works too — extract it and point
`ML_EXTRACTION_MODEL` / `ML_RISK_MODEL` / `ML_RECOMMENDATION_MODEL` in your `.env` at the
extracted folders' absolute paths instead of the HF repo ids. Not required for the Cloud Run path
above, which handles this on its own.)

## The plan

| Piece | Platform | Cost |
|---|---|---|
| Frontend (`web/`) | Vercel | Free |
| API + ML models | Google Cloud Run | Free at this traffic level, but needs a card on file |
| Database | Supabase | Free (already running) |

No Celery worker or Redis in this deployment. Cloud Run throttles CPU to near-zero *between*
requests unless you pay extra for "always allocated" CPU, which would starve a background
worker sitting idle on a queue. Instead, `/verify` runs the compliance pipeline inline within
the request when `SYNC_PIPELINE=true` (the Cloud Run Dockerfile sets this automatically) — a
few extra seconds of response time per verification, in exchange for correctness on this kind
of platform. This was tested locally (no Redis running, `SYNC_PIPELINE=true`) and confirmed
working before this guide was written; only the actual Cloud Run deploy itself is unverified.

## Step 1 — one-time GCP setup

1. Create a GCP project (or use an existing one) at https://console.cloud.google.com. It'll ask
   for a card — Cloud Run's free tier is genuinely generous for low traffic, but keep an eye on
   the billing dashboard for your first few days, since a card being on file means it *can*
   charge if usage spikes.
2. Install the `gcloud` CLI: https://cloud.google.com/sdk/docs/install
3. `gcloud auth login`
4. `gcloud config set project YOUR_PROJECT_ID`
5. One-time: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com`

## Step 2 — deploy the backend

From the repo root, on the `ml-model` branch, with your `.env` present (it reads `DATABASE_URL`
from there — never pass it as a command-line argument, it'd land in shell history):

```bash
./deploy/deploy_cloudrun.sh
```

This doesn't need Docker installed locally — `gcloud run deploy --source` uploads the source
and builds the container server-side via Cloud Build. Takes a few minutes the first time
(installing torch + transformers, plus longer still if it's also baking in `trained_models.zip`
— see above). It prints one of these two lines early on, so you know which path it took:

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

Check `.../health` returns `{"status":"ok"}`, then `.../tenders` returns real data. Try a
verification too:

```bash
curl -X POST https://<your-url>/bids/BID-B001-T2026-0001/verify
```

Should come back within a few seconds with `"status":"success"` and the full result inline
(no polling needed — that's the sync-pipeline behaviour described above).

## Step 3 — deploy the frontend to Vercel

1. https://vercel.com/new → import the GitHub repo (branch: `ml-model`, or wherever it lands after review).
2. **Root Directory**: `web` — this is the one setting that actually matters.
3. **Environment Variables**: `VITE_API_BASE_URL` = your Cloud Run URL from Step 2 (no trailing slash).
4. Deploy.

`web/vercel.json` already tells Vercel how to build it. No routing config needed — the app uses
hash-based URLs (`#/tenders/...`), which never touch the server.

## Step 4 — verify

Open the Vercel URL. You should see the tender list, live from Supabase via Cloud Run. Click
into a tender, then a bidder, to see the full detail page (score, documents, audit log, AI
recommendation), and try "Run verification" on a bid — it'll take a few seconds longer than it
did locally (the whole pipeline running inline, plus a cold start if the service had scaled to
zero), but should complete and show a result without needing to poll or refresh.

## Things that are normal, not bugs

- **Cold start**: Cloud Run scales to zero when idle. The first request after a quiet period
  takes longer (loading the models fresh — from the image directly if you baked in
  `trained_models.zip`, otherwise from Hugging Face). Subsequent requests are fast until it
  scales down again.
- **`/verify` takes longer than it used to**: expected, see above — it's now doing the whole
  pipeline inline instead of returning immediately with a job id.
- **Supabase pause**: free tier pauses after 7 days of zero activity. One request from the
  Supabase dashboard wakes it back up if that happens.
- **Uploaded documents don't persist**: they live on the container's local disk, which is wiped
  on every restart/redeploy — Cloud Run instances are stateless. Fine for a demo. Fixing it for
  real means swapping `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible
  one — not done here.

## Redeploying later

- Backend: `./deploy/deploy_cloudrun.sh` again.
- Frontend: push to GitHub — Vercel redeploys automatically if connected via the dashboard.

## If something breaks

`deploy/DEPLOY.md` has more background on the architecture decisions. Cloud Build's build log
(linked from the `gcloud run deploy` output, or in the GCP Console under Cloud Build → History)
is the first place to look if the deploy itself fails — that Dockerfile has never been run
against a real build before yours.
