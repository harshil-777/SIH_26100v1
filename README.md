# Bid-Auth

**Automated compliance verification for Government e-Marketplace (GeM) tender bids.**

Cross-checks every bidder's self-declarations against their uploaded documents and independent
government-portal records (Udyam, GSTN, PAN, MCA21, EPFO/ESIC, Startup India, NSIC, the debarment
registry, Make-in-India local-content rules), then produces a compliance score, a risk band, and
a tamper-evident, hash-chained decision trail for a procurement officer to act on. Three trained
ML models assist document reading, risk estimation and recommendation drafting — the rule engine
stays the auditable decision of record.

**Live demo:** [bid-auth.vercel.app](https://bid-auth.vercel.app) · API: [bid-auth-production.up.railway.app](https://bid-auth-production.up.railway.app/docs)
*(hosted on free tiers — the backend may take a few seconds to wake up after being idle)*

## What it does

- **Verifies eligibility** against a tender's mandatory and graded rules (MSME reservation,
  Make-in-India local content, EPFO compliance, debarment, document completeness, ...)
- **Cross-checks three independent sources** for every fact that matters — what the bidder
  declared, what their uploaded certificate says (OCR), and what the government portal reports —
  and flags any disagreement
- **Scores and bands risk**: any mandatory failure caps the score at 40 and marks the bid
  Non-Compliant; otherwise a weighted average of graded criteria bands into Low / Medium / High
- **Assists with ML, never decides with it**: a trained extractor reads certificates, a trained
  risk model estimates the outcome from what was actually observed (and explains why via
  per-feature contributions), and a trained writer drafts the officer recommendation — each with
  a guardrail that falls back to deterministic, rule-engine-derived output rather than risk a
  wrong or invented claim
- **Records everything tamper-evidently**: every verification run and officer decision is a
  SHA-256 hash-chained `audit_log` entry, checkable on demand (`GET /audit/verify` recomputes
  every chain and reports any break)
- **Gives officers a worklist**: a review queue grouped by tender (worst risk first), and a
  personal "mark to check later" flag on any bid

## Architecture

```
app/
  adapters/       One VerificationAdapter per government-portal source (mock or live, switched
                   by ADAPTER_MODE). All 9 wrap a mock registry loaded from seed/demo fixtures;
                   ADAPTER_MODE=live raises NotImplementedError (no real government API
                   integration -- out of scope, see WORKING DOCUMENTS/BUILD_SPEC.md section 10).
  models/         SQLAlchemy models, one file per table group (adds bid_marks)
  schemas/        Pydantic request/response schemas
  routers/        FastAPI routers: tenders, bids, dashboard, audit, marks
  services/
    orchestrator.py   Runs the 8-stage per-bid pipeline; reports stage_timings_ms
    ml_models.py        Lazy-loads the 3 trained models, thread-safe, warms up at startup;
                         every call degrades to None (non-ML behaviour) on any failure
    completeness.py    Stage 1: mandatory-document diff
    ocr.py              Stage 2: text extraction, then the trained extractor or a regex
                          parser for structured fields (GSTIN, PAN, Udyam, ...)
    verification.py      Stage 3: parallel portal adapter calls
    rule_engine.py         Stages 4-5: cross-verification + per-criterion evaluation
    scoring.py               Stage 6: compliance score + risk band (+ advisory ML risk estimate)
    recommendation.py         Stage 7: trained writer with a guardrail, template fallback
    audit.py                   Stage 8: sha256 hash-chained audit log
    object_store.py             Uploaded-file storage interface (local filesystem for dev)
  db/
    seed.py         Loads the 6 base fixture files (12 bids, deliberate compliance scenarios)
    seed_demo.py      Additively loads ~57 more generated bids and scores them for real
    migrations/      Alembic, schema per BUILD_SPEC.md section 3 (+0003: bid_marks)
  tasks.py         Celery tasks: the verification pipeline and per-upload OCR
ml/                Training pipeline for the 3 models (synthetic data, train, infer, push to
                   Hugging Face) -- see ml/README.md
scripts/
  generate_demo_bids.py     Generates a larger, varied demo bid set (fictitious identities)
  make_sample_documents.py   Generates sample certificates for testing uploads
  check_ground_truth.py      Runs all 12 seed bids end to end against their expected outcome
  verify_audit_chain.py      Walks the whole audit log in the DB and confirms no chain is broken
web/               React officer dashboard -- overview, tenders, bid detail, marked bids,
                   tender-wise audit trail (see "Frontend" below)
deploy/            Railway / Google Cloud Run / Hugging Face Space deploy scripts -- see
                   hosting_guide.md
tests/
  unit/            No database or network: rules, scoring, audit chain, OCR parsing, API errors
  integration/     Throwaway Postgres: all 12 seed bids end to end, uploads, decisions, audit
  ml/               Sanity checks on the ML training data generators
```

### The verification pipeline

`POST /bids/{bid_id}/verify` runs, in order (as a Celery task locally, or inline within the
request on platforms where a background worker can't reliably get CPU — see `SYNC_PIPELINE` in
`app/config.py`):

1. **Completeness** — diff submitted documents against the tender's mandatory requirements
2. **OCR** — extracts text from each uploaded document (PDF text layer, or Tesseract for
   images/scans), then the trained extraction model reads structured fields, falling back to a
   regex parser if the model is unavailable or fails; seeded placeholder documents are skipped
3. **Portal verification** — calls all 9 adapters concurrently, persists to `verification_results`
4. **Cross-verification** — per fact (enterprise category, local content %, GSTIN, trade name,
   ...), compares whichever of declaration / document / portal are available
5. **Rule engine** — evaluates the tender's mandatory/graded criteria against those facts. On an
   MSME-reserved tender, MSME eligibility is mandatory: a non-MSME bid is ineligible outright
6. **Scoring** — any failed mandatory criterion caps the score at 40 and forces `Non-Compliant`;
   otherwise a weighted average of graded criteria bands into Low (≥85) / Medium (60-84) / High
   (<60). The trained risk model's own estimate (with its top contributing features) is attached
   alongside as `ml_risk_estimate` — advisory only, it never changes the score or verdict
7. **Recommendation** — the trained writer drafts officer-facing text; a guardrail checks it
   states the correct verdict, mentions every real finding and invents none, falling back to a
   deterministic template built from the same findings if it fails that check
8. **Audit** — one hash-chained `audit_log` row per run (`curr_hash = sha256(prev_hash + payload)`)

## ML models

Three models, trained on synthetic data generated from the app's own rule engine (so labels
always match production logic), published to Hugging Face, loaded lazily and optionally —
`ML_MODELS_ENABLED=false` (the default for local dev) runs the exact pre-ML pipeline. Full
detail, training data generation and held-out results: [`ml/README.md`](ml/README.md).

| Model | What it does | Base | Hugging Face |
|---|---|---|---|
| Extraction | Reads certificate text, extracts GSTIN, PAN, Udyam no., CIN, EPFO code, dates, ... | `distilbert-base-cased` | [`HarshilDaGoat/gem-certificate-extractor`](https://huggingface.co/HarshilDaGoat/gem-certificate-extractor) |
| Risk | Estimates risk from what the pipeline actually observed; explains each estimate | LightGBM | [`HarshilDaGoat/gem-bid-risk`](https://huggingface.co/HarshilDaGoat/gem-bid-risk) |
| Recommendation | Drafts the officer recommendation from the score breakdown | `flan-t5-small` | [`HarshilDaGoat/gem-recommendation-writer`](https://huggingface.co/HarshilDaGoat/gem-recommendation-writer) |

## Frontend

React + TypeScript + Vite + Tailwind, hash-routed (no server-side routing needed):

| Route | Page |
|---|---|
| `#/` | Overview — KPIs, review queue grouped by tender, risk-by-tender, marked bids, latest activity |
| `#/tenders` | Searchable, sortable tender list with deadline and risk-profile at a glance |
| `#/tenders/:id` | Tender detail — bidder ranking, scoring rubric, participants, required documents |
| `#/bids/:id` | Bid detail — score, criteria breakdown, cross-verification, documents, portal checks, officer decision panel, audit chain |
| `#/marked` | Every bid an officer has flagged to check later |
| `#/audit` | Audit trail — pick a tender, see its history bid by bid, plus a global integrity check |

Global search (`Ctrl/⌘K`) finds tenders and bidders by name, ID or department.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/tenders` | Create a tender |
| GET | `/tenders` | Tender list with participant/risk summary (landing page) |
| GET | `/tenders/{tender_id}` | Tender detail |
| GET | `/tenders/{tender_id}/document-requirements` | Required documents for a tender |
| POST | `/bids` | Create a bid |
| GET | `/bids/{bid_id}` | Bid detail: bidder, tender, declarations, latest result per portal |
| POST | `/bids/{bid_id}/documents` | Multipart upload (`document_type`, `file`, optional `note`): PDF/PNG/JPEG/TIFF up to 10 MB, OCR queued. Omit `file` to record a non-submission |
| GET | `/bids/{bid_id}/documents` | Submissions with their latest upload and OCR result |
| POST | `/bids/{bid_id}/declarations` | Submit/update a bidder self-declaration |
| POST | `/bids/{bid_id}/verify` | Run the verification pipeline (queued, or inline — see above) |
| GET | `/bids/{bid_id}/status` | Poll pipeline job status |
| GET | `/bids/{bid_id}/compliance-score` | Latest score + criterion breakdown |
| GET | `/bids/{bid_id}/audit-log` | Full hash-chained history for one bid (chain-verified) |
| POST | `/bids/{bid_id}/decision` | Officer action: qualify / disqualify / request clarification (a reason is required for the last two) |
| PUT / DELETE | `/bids/{bid_id}/mark` | Flag or unflag a bid to check later |
| GET | `/marks` | Every currently marked bid |
| GET | `/dashboard/bids?tender_id=` | List view for the procurement officer dashboard |
| GET | `/audit/verify` | Recompute every bid's hash chain and report any break |
| GET | `/audit/tenders` | Per-tender audit rollup (bid/verification/decision counts, last activity) |
| GET | `/audit/recent?tender_id=` | Newest audit entries, optionally scoped to one tender |

Interactive docs at `/docs` once the API is running (also live at the demo API link above).

## Running it locally

**Quickest — everything in Docker, nothing external:**

```bash
cp .env.example .env          # leave DATABASE_URL unset to use the bundled postgres
docker compose up -d          # postgres, redis, api (:8000), worker, dashboard (:5173)
docker compose exec api python -m alembic upgrade head
docker compose exec api python -m app.db.seed
```

Then open http://localhost:5173. To use Supabase or another external Postgres instead, set
`DATABASE_URL` in `.env`; it takes precedence over the bundled one.

**Or run the Python side directly.** You need a Postgres database and, for the `/verify`
endpoint specifically, Redis (via Docker Compose, or any Redis-compatible host). If Redis is
down, `/verify` returns 503 and uploads still succeed. For image/scanned-PDF OCR outside Docker,
install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (the Docker image already
has it).

```bash
cp .env.example .env   # fill in DATABASE_URL etc.
pip install -r requirements.txt

python -m alembic upgrade head   # create schema (re-run after pulling: new migrations apply)
python -m app.db.seed             # load the 6 base fixture bids
python -m app.db.seed_demo         # optional: add ~57 more generated bids, scored for real

uvicorn app.main:app --reload     # API on :8000
```

```bash
docker compose up -d redis worker   # background pipeline jobs
```

```bash
cd web && npm install && npm run dev   # frontend on :5173
```

To turn on the trained models, set `ML_MODELS_ENABLED=true` (needs `torch`/`transformers`
installed and a first-run download from Hugging Face, or `trained_models.zip` — see
`hosting_guide.md`).

## Deploying it

Full, tested walkthrough (Railway or Google Cloud Run for the backend, Vercel for the frontend,
all free-tier): [`hosting_guide.md`](hosting_guide.md). Background on the platform-specific
decisions (why no background worker on serverless, connection pooling, region placement):
[`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Demo / seed data

`python -m app.db.seed` loads 6 tenders and 12 bidders spanning a deliberate range of compliance
scenarios (clean bid, cancelled GSTIN, invalid PAN, debarred entity, missing mandatory document,
local-content shortfall, EPFO employee-count mismatch, expired startup recognition,
document/portal name mismatch, MSME-reservation ineligibility, ...) from
[`WORKING DOCUMENTS/`](WORKING%20DOCUMENTS/) — see the `scenario_tag` / `expected_ground_truth`
columns in `dummy_bidders.csv`.

`python scripts/generate_demo_bids.py` generates a larger, varied set (fictitious identities, a
realistic mix of the same kinds of real-world defects) on top of that, and
`python -m app.db.seed_demo` loads and scores it through the real pipeline — additive, never
truncates, safe to run against a database that already has real data.

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                         # unit tests; integration tests skip without a test database

docker compose up -d postgres  # throwaway test database lives on the bundled postgres
TEST_DATABASE_URL=postgresql+asyncpg://gem:gem@localhost:5433/gem_compliance_test pytest

docker compose run --rm test   # the whole suite inside the Docker image (includes Tesseract OCR)
```

The integration tests migrate, wipe and reseed the database in `TEST_DATABASE_URL`, so it must
be a disposable one whose name ends in `_test` — anything else is refused. Tests never use
`DATABASE_URL`, so they can't touch a shared database.

Check a running deployment end to end (API and worker must be running):

```bash
python scripts/check_ground_truth.py   # re-verifies all 12 seed bids; expect "12/12 ... match"
python scripts/verify_audit_chain.py   # expect "OK: every chain verifies"
```

## Tech stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2
- **Async jobs**: Celery + Redis locally; inline execution on serverless deploys (see above)
- **Database**: PostgreSQL — the Compose stack's own `postgres` service, or an external one
  (this project runs its hosted demo on [Supabase](https://supabase.com)) via `DATABASE_URL`
- **ML**: PyTorch + Transformers (DistilBERT, flan-t5-small), LightGBM, published to Hugging Face
- **OCR**: pdfplumber for PDF text layers, Tesseract for images and scanned PDFs
- **Object storage**: local `./storage/` behind an `ObjectStore` interface (S3/MinIO-ready)
- **Frontend**: React + TypeScript, Vite, TailwindCSS, Recharts
- **Hosting**: Railway or Google Cloud Run (API), Vercel (frontend) — see `hosting_guide.md`
- **Containerization**: Docker Compose (`postgres` + `redis` + `worker` + `api` + `web`, plus an
  on-demand `test` service) for local development
- **Tests**: pytest, 117 tests (91 unit, 26 integration — the latter need a throwaway Postgres)
