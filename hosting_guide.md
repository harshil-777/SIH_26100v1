# Hosting guide

Everything needed to put this online for free, written for whoever's picking this up on a
machine with working Docker (it doesn't work on the machine that built this branch, so none of
the steps below involving a real `docker build` have been run for real yet — you're the first
real test).

## What's already done

- Branch: `ml-model`. Pull it: `git checkout ml-model && git pull`
- Three trained models are already public on Hugging Face and need no further action:
  [extraction](https://huggingface.co/HarshilDaGoat/gem-certificate-extractor),
  [risk](https://huggingface.co/HarshilDaGoat/gem-bid-risk),
  [recommendation](https://huggingface.co/HarshilDaGoat/gem-recommendation-writer). The backend
  downloads them at startup (`ML_MODELS_ENABLED=true`, already the default in the deploy config).
- Database: Supabase, already set up and seeded. You'll just need the `DATABASE_URL`.

## The plan

| Piece | Platform | Cost |
|---|---|---|
| Frontend (`web/`) | Vercel | Free |
| API + Celery worker + Redis + models | Hugging Face Spaces (Docker) | Free (CPU, 16GB RAM) |
| Database | Supabase | Free (already running) |

## Step 0 — build-test the backend image locally first

This is the one thing your working Docker can do that couldn't be done before: catch a broken
Dockerfile before pushing it and waiting on Hugging Face's build queue.

```bash
mkdir -p /tmp/space-test && cd /tmp/space-test
cp -r /path/to/repo/app .
cp /path/to/repo/alembic.ini .
cp /path/to/repo/requirements.txt .
cp -r "/path/to/repo/WORKING DOCUMENTS" .
cp /path/to/repo/deploy/space/Dockerfile .
cp /path/to/repo/deploy/space/start.sh .

docker build -t gem-space-test .
docker run --rm -p 7860:7860 -e DATABASE_URL="<your supabase url>" gem-space-test
# then in another terminal:
curl http://localhost:7860/health
```

If that returns `{"status":"ok"}`, the image is good — skip straight to Step 1. If the build or
run fails, fix `deploy/space/Dockerfile` / `deploy/space/start.sh` in the repo, re-run this, and
only push once it works locally.

(This is exactly what `deploy/push_to_space.sh` assembles automatically for you when you deploy
for real — this step is just doing it by hand once, with your own eyes on the output.)

## Step 1 — create the Hugging Face Space

1. https://huggingface.co/new-space
2. SDK: **Docker**, hardware: free CPU basic. Name it whatever you like (e.g. `gem-compliance-api`).
3. **Settings → Variables and secrets → New secret**: `DATABASE_URL` = the Supabase connection
   string (ask Harshil for it if you don't have it — don't post it anywhere public).

## Step 2 — push the backend to it

From the repo root, on the `ml-model` branch:

```bash
./deploy/push_to_space.sh https://huggingface.co/spaces/YOUR_USERNAME/gem-compliance-api
```

It'll prompt for git credentials: username can be anything, password is a Hugging Face **write**
token (Settings → Access Tokens on huggingface.co). This pushes only the files the container
needs into the Space's own separate git repo (not your GitHub history) — a fresh single commit
each time, which is intentional.

Watch the build on the Space's own page. First build is slow (installing torch + transformers).
Once it says "Running", the API is live at:

```
https://YOUR_USERNAME-gem-compliance-api.hf.space
```

Check `.../health` returns `{"status":"ok"}`, then `.../tenders` returns real data.

## Step 3 — deploy the frontend to Vercel

1. https://vercel.com/new → import the GitHub repo (branch: `ml-model`, or wherever it lands after review).
2. **Root Directory**: `web` — this is the one setting that actually matters.
3. **Environment Variables**: `VITE_API_BASE_URL` = your Space's URL from Step 2 (no trailing slash).
4. Deploy.

`web/vercel.json` already tells Vercel how to build it. No routing config needed — the app uses
hash-based URLs (`#/tenders/...`), which never touch the server.

## Step 4 — verify

Open the Vercel URL. You should see the tender list, live from Supabase via your Space. Click
into a tender, then a bidder, to see the full detail page (score, documents, audit log,
AI recommendation).

## Things that are normal, not bugs

- **Space cold start**: after inactivity, the free tier sleeps. First request after that takes
  ~30-60s while it wakes up and reloads the models. Not a hang.
- **Supabase pause**: free tier pauses after 7 days of zero activity. One request from the
  Supabase dashboard wakes it back up if that happens.
- **Uploaded documents don't persist**: they live on the Space's local disk, which is wiped on
  every restart/redeploy. Fine for a demo. Fixing it for real means swapping
  `app/services/object_store.py`'s `LocalObjectStore` for an S3-compatible one — not done here.

## Redeploying later

- Backend: `./deploy/push_to_space.sh <space-url>` again.
- Frontend: push to GitHub — Vercel redeploys automatically if connected via the dashboard.

## If something breaks

The Space's build/run logs (on its own HF page) and `deploy/DEPLOY.md` (more background on the
architecture decisions here) are the first two places to look. Ping Harshil if the Dockerfile
itself needs a fix — it was written without ever running against a real Docker daemon, so if
Step 0 above surfaces a problem, that's expected and worth reporting back.
