# GeM Bid Compliance Platform

An automated compliance-verification pipeline for GeM (Government e-Marketplace) tender
bids. Cross-checks bidder self-declarations against uploaded documents and independent
government-portal data (Udyam, GSTN, PAN, MCA21, EPFO/ESIC, Startup India, NSIC, the
debarment registry, and Make-in-India local-content rules), then produces a compliance
score, a risk band, and an auditable, hash-chained decision trail for a procurement
officer to act on.

Full architecture and phase-by-phase build spec: [`WORKING DOCUMENTS/BUILD_SPEC.md`](WORKING%20DOCUMENTS/BUILD_SPEC.md).

## Status

| Phase | Scope | Status |
|---|---|---|
| 0 | Schema, seed data, scaffold | ✅ Done |
| 1 | Core verification pipeline against seed data | ✅ Done |
| 2 | Real uploads + OCR | Not started |
| 3 | Dashboard + officer actions (frontend) | Scaffolded only |
| 4 | Polish (recommendation UI, hash-chain viewer) | Not started |

## Tech stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2
- **Async jobs**: Celery + Redis — every adapter/OCR/AI call runs as a background task
- **Database**: PostgreSQL 15+ (this project runs it on [Supabase](https://supabase.com))
- **Frontend**: React + TypeScript, Vite, TailwindCSS
- **Containerization**: Docker Compose (`redis` + `worker` + `api` + `web`; Postgres is
  external, not containerized)

## Architecture

```
app/
  adapters/       One VerificationAdapter per government-portal source (mock or live,
                   switched by ADAPTER_MODE). All 9 currently wrap a mock registry
                   loaded from the seed fixture; ADAPTER_MODE=live raises
                   NotImplementedError (no real government API integration — out of
                   scope, see BUILD_SPEC.md section 10).
  models/         SQLAlchemy models, one file per table group
  schemas/        Pydantic request/response schemas
  routers/        FastAPI routers (tenders, bids, dashboard)
  services/
    orchestrator.py   Runs the 8-stage per-bid pipeline
    completeness.py    Stage 1: mandatory-document diff
    ocr.py              Stage 2: document extraction (no-op until Phase 2)
    verification.py      Stage 3: parallel portal adapter calls
    rule_engine.py         Stages 4–5: cross-verification + per-criterion evaluation
    scoring.py               Stage 6: compliance score + risk band
    recommendation.py         Stage 7: advisory text (deterministic stub for now)
    audit.py                   Stage 8: sha256 hash-chained audit log
  db/
    seed.py         Loads the six fixture files into Postgres
    migrations/      Alembic, schema per BUILD_SPEC.md section 3
  tasks.py         Celery task wrapping the orchestrator
web/               React dashboard (bid list; detail views are Phase 3)
```

### The verification pipeline

`POST /bids/{bid_id}/verify` enqueues a Celery task that runs, in order:

1. **Completeness** — diff submitted documents against the tender's mandatory requirements
2. **OCR** — extracts fields from uploaded documents (no-op until Phase 2 has real files)
3. **Portal verification** — calls all 9 adapters concurrently, persists to `verification_results`
4. **Cross-verification** — compares declaration vs. document vs. portal facts per criterion
5. **Rule engine** — evaluates the tender's mandatory/graded criteria against those facts
6. **Scoring** — any failed mandatory criterion caps the score at 40 and forces
   `Non-Compliant`; otherwise a weighted average of graded criteria bands into
   Low (≥85) / Medium (60–84) / High (<60)
7. **Recommendation** — advisory-only text for the dashboard, never a persisted decision
8. **Audit** — one hash-chained `audit_log` row per run (`curr_hash = sha256(prev_hash + payload)`)

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/tenders` | Create a tender |
| GET | `/tenders/{tender_id}` | Tender detail |
| GET | `/tenders/{tender_id}/document-requirements` | Required documents for a tender |
| POST | `/bids` | Create a bid |
| POST | `/bids/{bid_id}/documents` | Register a document submission |
| POST | `/bids/{bid_id}/declarations` | Submit/update a bidder self-declaration |
| POST | `/bids/{bid_id}/verify` | Enqueue the verification pipeline |
| GET | `/bids/{bid_id}/status` | Poll pipeline job status |
| GET | `/bids/{bid_id}/compliance-score` | Latest score + criterion breakdown |
| GET | `/bids/{bid_id}/audit-log` | Full hash-chained history (chain-verified) |
| POST | `/bids/{bid_id}/decision` | Officer action: qualify / disqualify / request clarification |
| GET | `/dashboard/bids?tender_id=` | List view for the procurement officer dashboard |

Interactive docs at `/docs` once the API is running.

## Running it

You need a Postgres database (Supabase works well — see the free tier) and, for the
`/verify` endpoint specifically, Redis (via Docker Compose, or any Redis-compatible host).

```bash
cp .env.example .env   # fill in DATABASE_URL etc.
pip install -r requirements.txt

python -m alembic upgrade head   # create schema
python -m app.db.seed             # load the 6 fixture files

uvicorn app.main:app --reload     # API on :8000
```

```bash
docker compose up -d redis worker   # background pipeline jobs
```

```bash
cd web && npm install && npm run dev   # frontend on :5173
```

## Seed data

Six fixture files under [`WORKING DOCUMENTS/`](WORKING%20DOCUMENTS/) define 6 tenders,
12 bidders, and 12 bids spanning a deliberate range of compliance scenarios (clean bid,
cancelled GSTIN, invalid PAN, debarred entity, missing mandatory document, local-content
shortfall, EPFO employee-count mismatch, expired startup recognition, document/portal
name mismatch, MSME-reservation ineligibility, and more) — see the `scenario_tag` /
`expected_ground_truth` columns in `dummy_bidders.csv`. `python -m app.db.seed` loads
these directly; no synthetic data is invented beyond the debarment registry, which the
build spec explicitly asks to pad with 2–3 fictional rows.
