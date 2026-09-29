# Deploying for free

Two pieces, two free platforms:

| Piece | Platform | Why |
|---|---|---|
| Frontend (`web/`) | Vercel | Built for static/Vite sites; zero cost |
| API + Celery worker + Redis + ML models | Hugging Face Spaces (Docker) | Free CPU tier, 16GB RAM — enough for the models; your models already live there |

Database stays on Supabase (already set up, already free).

## 1. Backend — Hugging Face Space

**Create the Space:**
1. https://huggingface.co/new-space
2. Pick a name (e.g. `gem-compliance-api`), SDK: **Docker**, hardware: free CPU basic.
3. Once created, go to **Settings → Variables and secrets** and add a secret:
   - `DATABASE_URL` = your Supabase connection string (same value as in your local `.env`)

**Push the code** (from this repo, on your machine):
```bash
./deploy/push_to_space.sh https://huggingface.co/spaces/YOUR_USERNAME/gem-compliance-api
```
It'll ask for git credentials on push — username can be anything, password is a Hugging Face
**write** token (Settings → Access Tokens on huggingface.co).

This only pushes what the container needs (`app/`, `alembic.ini`, `requirements.txt`, seed
data, the Dockerfile) into the Space's own separate git repo — not your whole GitHub repo, and
not your GitHub history. Every run force-pushes a fresh single commit; that's intentional, the
Space is a deploy target, not somewhere to keep history.

**Watch it build:** the Space's own page shows build logs. First build takes a while (installing
torch + transformers). Once it says "Running", your API is live at:
```
https://YOUR_USERNAME-gem-compliance-api.hf.space
```
Check `https://.../health` returns `{"status":"ok"}`.

## 2. Frontend — Vercel

1. https://vercel.com/new → import your GitHub repo.
2. **Root Directory**: set to `web` (this is the one setting that matters — the repo has other
   top-level folders Vercel would otherwise get confused by).
3. **Environment Variables**: add
   - `VITE_API_BASE_URL` = `https://YOUR_USERNAME-gem-compliance-api.hf.space` (your Space's URL from step 1, no trailing slash)
4. Deploy.

Vercel auto-detects Vite from `web/vercel.json` (already in the repo). No server-side routing
config needed — the app uses hash-based URLs (`#/tenders/...`), which never touch the server, so
there's no SPA-rewrite/404-on-refresh problem to solve.

## 3. Verify

Open your Vercel URL. It should show the tender list, pulling live from your Space's API, which
pulls from Supabase and loads your three models from Hugging Face on first request (a few
seconds of cold-start the very first time; cached after that for as long as the Space stays warm).

## What's free and what to watch

- **Vercel free tier**: unlimited for personal projects, generous bandwidth.
- **HF Spaces free CPU tier**: the Space sleeps after a period of inactivity and cold-starts on
  the next request (expect ~30-60s the first time it wakes, since it re-downloads/re-loads the
  models). That's normal, not a bug.
- **Supabase free tier**: has its own inactivity pause after 7 days with zero activity — if that
  happens, one request from the dashboard/Supabase UI wakes it back up.
- **Storage caveat**: uploaded documents live on the Space's local disk, which is wiped on every
  restart/redeploy (see `deploy/space/README.md`). Fine for a demo; not for anything you need to
  keep. Fixing this for real means swapping `LocalObjectStore` for an S3-compatible one in
  `app/services/object_store.py` — not done here since it's out of scope for "free."

## Redeploying after a code change

Backend: `./deploy/push_to_space.sh <space-url>` again.
Frontend: push to GitHub — Vercel redeploys automatically on every push (if you connected the
repo via the Vercel dashboard as in step 2).
