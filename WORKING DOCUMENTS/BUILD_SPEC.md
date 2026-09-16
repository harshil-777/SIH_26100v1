# GeM Bid Compliance Platform — Build Spec

Target reader: an IDE coding agent. This file is directive, not explanatory — for rationale and
the full architecture discussion, see `gem-compliance-platform-guide.md` in the same drop. Follow
this spec literally; where it's silent, prefer the simplest thing that passes the Definition of
Done for that phase.

Load these seed files from the same folder before Phase 1: `dummy_tenders.csv`,
`dummy_bidders.csv`, `dummy_tender_document_requirements.csv`, `dummy_bid_document_submissions.csv`,
`dummy_bid_declarations.csv`, `dummy_mock_portal_responses.json`.

---

## 1. Tech stack (locked — do not substitute)

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2. Single modular monolith
  (`app/` with internal module boundaries by domain, not separate services).
- **Async jobs**: Celery + Redis. Every adapter call and every AI/OCR call runs as a task, never
  inline in a request handler.
- **Database**: PostgreSQL 15+.
- **Frontend**: React + TypeScript, Vite, TailwindCSS, shadcn/ui, Recharts.
- **Object storage**: local filesystem under `./storage/` for dev; interface it behind an
  `ObjectStore` class so swapping to S3/MinIO later is a one-file change.
- **Containerization**: `docker-compose.yml` with services `api`, `worker`, `postgres`, `redis`,
  `web`.

---

## 2. Repository layout

```
/app
  /adapters          # one file per VerificationAdapter, + mock_registry.py
  /models             # SQLAlchemy models, one file per table group
  /schemas            # Pydantic request/response schemas
  /routers            # FastAPI routers, one file per resource
  /services
    orchestrator.py    # runs the per-bid pipeline (§7)
    rule_engine.py      # evaluates tender_document_requirements + criteria JSON (§8)
    scoring.py           # compliance score + risk band
    ocr.py                # document extraction
    recommendation.py     # LLM call, structured input only
  /db
    seed.py             # loads the six seed files into Postgres
    migrations/          # alembic
  main.py
/web                  # React app
/storage              # uploaded files (dev only)
docker-compose.yml
.env.example
```

---

## 3. Database schema (Postgres DDL)

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','procurement_officer','auditor','bidder')),
    department TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenders (
    tender_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Goods','Services')),
    estimated_value_inr NUMERIC NOT NULL,
    msme_reserved BOOLEAN NOT NULL DEFAULT FALSE,
    mii_local_content_threshold_pct NUMERIC,
    requires_oem_authorization BOOLEAN NOT NULL DEFAULT FALSE,
    epfo_applicable_employee_threshold INT,
    submission_deadline DATE NOT NULL,
    eligibility_rules_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bidders (
    bidder_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pan TEXT NOT NULL,
    gstin TEXT,
    udyam_number TEXT,
    cin TEXT,
    dpiit_recognition_number TEXT,
    nsic_registration_number TEXT,
    epfo_establishment_code TEXT,
    employee_count INT,
    enterprise_category TEXT CHECK (enterprise_category IN ('Micro','Small','Medium','Large')),
    state TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bids (
    bid_id TEXT PRIMARY KEY,
    tender_id TEXT NOT NULL REFERENCES tenders(tender_id),
    bidder_id TEXT NOT NULL REFERENCES bidders(bidder_id),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted','under_review','qualified','disqualified','clarification_requested')),
    UNIQUE(tender_id, bidder_id)
);

CREATE TABLE document_types (
    type_code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    applies_to_category TEXT
);

CREATE TABLE tender_document_requirements (
    requirement_id TEXT PRIMARY KEY,
    tender_id TEXT NOT NULL REFERENCES tenders(tender_id),
    document_type TEXT NOT NULL REFERENCES document_types(type_code),
    buyer_label TEXT,
    requirement_source TEXT NOT NULL
        CHECK (requirement_source IN ('system_template','buyer_selected_turnover_experience','buyer_atc','corrigendum')),
    mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

CREATE TABLE bid_document_submissions (
    submission_id TEXT PRIMARY KEY,
    bid_id TEXT NOT NULL REFERENCES bids(bid_id),
    bidder_id TEXT NOT NULL REFERENCES bidders(bidder_id),
    tender_id TEXT NOT NULL REFERENCES tenders(tender_id),
    document_type TEXT NOT NULL REFERENCES document_types(type_code),
    submitted BOOLEAN NOT NULL,
    file_ref TEXT,
    note TEXT
);

CREATE TABLE bid_declarations (
    declaration_id TEXT PRIMARY KEY,
    bid_id TEXT NOT NULL REFERENCES bids(bid_id),
    bidder_id TEXT NOT NULL REFERENCES bidders(bidder_id),
    tender_id TEXT NOT NULL REFERENCES tenders(tender_id),
    criterion_code TEXT NOT NULL,
    declared_value TEXT NOT NULL,
    declared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note TEXT
);

CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id TEXT NOT NULL REFERENCES bids(bid_id),
    doc_type TEXT NOT NULL REFERENCES document_types(type_code),
    file_url TEXT NOT NULL,
    ocr_extracted_json JSONB,
    file_hash TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE verification_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id TEXT NOT NULL REFERENCES bids(bid_id),
    source TEXT NOT NULL,  -- udyam | gstn | pan | mca21 | epfo_esic | startup_india | nsic | debarment | mii_local_content
    status TEXT NOT NULL,
    raw_response_json JSONB,
    confidence_score NUMERIC,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE compliance_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id TEXT NOT NULL REFERENCES bids(bid_id),
    overall_score NUMERIC NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('Low','Medium','High','Non-Compliant')),
    criterion_breakdown_json JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE debarred_entities (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pan TEXT,
    gstin TEXT,
    name TEXT NOT NULL,
    order_reference TEXT,
    debarred_from DATE,
    debarred_until DATE,
    list_source TEXT
);

CREATE TABLE audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    bid_id TEXT REFERENCES bids(bid_id),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_json JSONB,
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash TEXT,
    curr_hash TEXT NOT NULL
);
```

`document_types` rows to seed (derive distinct values from the two requirement/submission CSVs —
don't hand-maintain a second list): `OEM_AUTHORIZATION_LETTER`, `MII_LOCAL_CONTENT_SELF_CERTIFICATE`,
`TURNOVER_CERTIFICATE_CA`, `EMD_EXEMPTION_PROOF`, `PAST_EXPERIENCE_PROOF`,
`EPFO_ESIC_COMPLIANCE_CERTIFICATE`, `QUALITY_BIS_CERTIFICATE`, `PSARA_LICENSE`, `GST_CERTIFICATE`,
`STARTUP_EMD_EXEMPTION_PROOF`, `PAN_CARD`, `UDYAM_CERTIFICATE`.

---

## 4. Seed data — exact mapping from CSV/JSON to tables

Write `app/db/seed.py` to do this, in order (foreign keys require this order):

1. **`tenders`** ← `dummy_tenders.csv`, one row per row, column names match directly.
2. **`bidders`** ← `dummy_bidders.csv`, columns `bidder_id..state` match directly. Ignore
   `target_tender_id`, `scenario_tag`, `expected_ground_truth` here — they drive step 3 and are
   test-fixture metadata, not bidder attributes.
3. **`bids`** — derive one row per bidder from `dummy_bidders.csv`: `bid_id = f"BID-{bidder_id}-{target_tender_id}"`,
   `tender_id = target_tender_id`. This must produce exactly the `bid_id` values already used in
   `dummy_bid_document_submissions.csv` and `dummy_bid_declarations.csv` — don't regenerate IDs.
4. **`document_types`** — populate from the distinct `document_type` values across
   `dummy_tender_document_requirements.csv` and `dummy_bid_document_submissions.csv`.
5. **`tender_document_requirements`** ← `dummy_tender_document_requirements.csv` directly (skip
   lines starting with `#`).
6. **`bid_document_submissions`** ← `dummy_bid_document_submissions.csv` directly (skip `#` lines).
7. **`bid_declarations`** ← `dummy_bid_declarations.csv` directly (skip `#` lines).
8. **`verification_results`** — for each bidder in `dummy_mock_portal_responses.json`, for each
   non-`not_applicable` adapter key, insert one row per bid where `bidder_id` matches (`source` =
   the JSON key, e.g. `udyam`, `gstn`; `raw_response_json` = the object verbatim; `status` and
   `confidence` pulled out of it). This is what the mock adapter backend also reads from directly
   at runtime (§5) — seeding it into `verification_results` too just means the dashboard has
   something to show without re-running the pipeline.
9. **`debarred_entities`** — one row, from bidder B005 in the mock JSON (`order_reference`
   `DGS&D/DEBAR/2025/0091`, `debarred_until` `2027-05-31`). Add 2–3 more fictional rows so the
   debarment adapter isn't trivially a single-row lookup.
10. **`documents`** — synthetic rows only where a submission's `submitted = TRUE`, `file_url` =
    the `file_ref` from `dummy_bid_document_submissions.csv` (these are placeholder paths, not
    real files — Phase 2 replaces this with real OCR output once real uploads exist).

---

## 5. Core interfaces

```python
# app/adapters/base.py
from typing import Protocol, TypedDict, Any

class VerificationResult(TypedDict, total=False):
    status: str
    confidence: float
    verified_at: str
    raw: dict[str, Any]

class VerificationAdapter(Protocol):
    source_name: str
    def verify(self, bidder_id: str) -> VerificationResult: ...
```

```python
# app/adapters/mock_registry.py
# Loads dummy_mock_portal_responses.json once at startup. verify(source, bidder_id) looks up
# bidders[bidder_id][source] and returns it, defaulting to {"status": "not_checked"} for a
# source/bidder pair absent from the fixture. Every concrete adapter (UdyamAdapter, GstnAdapter,
# ...) wraps this registry when ADAPTER_MODE=mock (the default) and calls a real client when
# ADAPTER_MODE=live. Business logic (rule engine, scoring, dashboard) only ever talks to the
# VerificationAdapter interface and must not know which mode is active.
```

Selection is a factory keyed off `ADAPTER_MODE` env var, not a code branch scattered through the
orchestrator:

```python
# app/adapters/__init__.py
def get_adapter(source_name: str) -> VerificationAdapter: ...
```

---

## 6. API endpoints (Phase 1 minimum set)

| Method | Path | Purpose |
|---|---|---|
| POST | `/tenders` | Create a tender |
| GET | `/tenders/{tender_id}` | Tender detail |
| GET | `/tenders/{tender_id}/document-requirements` | List `tender_document_requirements` for it |
| POST | `/bids` | Create a bid (bidder + tender) |
| POST | `/bids/{bid_id}/documents` | Register a document submission (multipart upload in Phase 2; Phase 1 can accept a file reference) |
| POST | `/bids/{bid_id}/declarations` | Submit/update `bid_declarations` rows |
| POST | `/bids/{bid_id}/verify` | Enqueue the orchestrator pipeline (§7) as a Celery task; returns immediately with a job id |
| GET | `/bids/{bid_id}/status` | Poll job/pipeline status |
| GET | `/bids/{bid_id}/compliance-score` | Latest `compliance_scores` row + `criterion_breakdown_json` |
| GET | `/bids/{bid_id}/audit-log` | Full hash-chained history for this bid |
| POST | `/bids/{bid_id}/decision` | Officer action: `qualify` / `disqualify` / `request_clarification`; writes to `audit_log` |
| GET | `/dashboard/bids?tender_id=` | List view: bid, bidder, score, risk badge, status |

---

## 7. Orchestrator pipeline (`app/services/orchestrator.py`)

Run in this exact order per bid; each stage's output feeds the next and is persisted before moving
on (so a crash mid-pipeline can resume, not restart):

1. **Completeness check** — diff `bid_document_submissions` (mandatory=TRUE rows only) against
   `tender_document_requirements` for this bid's tender. Missing mandatory items → immediate
   mandatory-failure flags, still continue the pipeline (the officer should see everything, not
   just the first failure).
2. **OCR / extraction** — for each `submitted=TRUE` document, run `services/ocr.py`, write result
   to `documents.ocr_extracted_json`. Phase 1 with seed data: this step is a no-op read of
   pre-populated `ocr_extracted_json` since there are no real files yet.
3. **Portal verification** — call every adapter in parallel (`asyncio.gather`, not sequential
   awaits) via `get_adapter(source).verify(bidder_id)`, persist each to `verification_results`.
4. **Three-way cross-verification** — for every criterion with more than one of
   {declaration, document, portal} available, compare. Persist per-criterion match/mismatch to
   `criterion_breakdown_json` (not a separate table — it's an artifact of this bid's scoring run).
5. **Rule engine** — evaluate the tender's criteria config (§8) against the accumulated facts.
6. **Scoring** — `services/scoring.py` computes `overall_score` + `risk_level`, writes
   `compliance_scores`.
7. **Recommendation** — `services/recommendation.py` sends the *structured* score breakdown (never
   raw documents) to the LLM, returns advisory text for the dashboard. Never persisted as a
   decision — display-only, labeled "AI-generated, advisory only" in the API response.
8. **Audit write** — one `audit_log` row for the whole run, `curr_hash = sha256(prev_hash + json.dumps(payload, sort_keys=True))`.

---

## 8. Rule engine config format

One JSON blob per tender, stored in `tenders.eligibility_rules_json`:

```json
{
  "criteria": [
    {"id": "gst_active", "type": "mandatory", "source": "verification_results.gstn.status==active"},
    {"id": "not_debarred", "type": "mandatory", "source": "verification_results.debarment.status==clear"},
    {"id": "pan_valid", "type": "mandatory", "source": "verification_results.pan.status==valid"},
    {"id": "document_completeness", "type": "mandatory", "source": "completeness_check"},
    {"id": "local_content_pct", "type": "graded", "weight": 0.25, "threshold": 50, "source": "verification_results.mii_local_content.verified_pct_estimate"},
    {"id": "epfo_compliance", "type": "graded", "weight": 0.10, "source": "cross_check.epfo_esic"}
  ]
}
```

Scoring: any `mandatory` criterion failing caps `overall_score` at 40 and forces
`risk_level = 'Non-Compliant'`. Otherwise sum `graded` criteria by weight into a 0–100 score, band
into Low (≥85) / Medium (60–84) / High (<60).

---

## 9. Build order — phases and Definition of Done

**Phase 0 — Setup**
DoD: `docker-compose up` brings up api+worker+postgres+redis+web; `alembic upgrade head` applies
the schema in §3; `python -m app.db.seed` loads all six fixture files without error;
`GET /dashboard/bids` returns 12 rows (empty scores, since nothing's been verified yet).

**Phase 1 — Core pipeline against seed data**
DoD: `POST /bids/{bid_id}/verify` for bid `BID-B001-T2026-0001` runs the full 8-stage pipeline
against the mock adapter registry and seeded declarations/submissions, and produces a
`compliance_scores` row with `risk_level = 'Low'`. Running it for `BID-B002-T2026-0003` produces
`risk_level = 'Non-Compliant'` with `mandatory_failure_reason` traceable to the GSTN adapter's
`cancelled` status. Running it for `BID-B012-T2026-0001` flags the missing
`OEM_AUTHORIZATION_LETTER` from the completeness check, not from any adapter.

**Phase 2 — Real uploads + OCR**
DoD: a real PDF/image upload through `POST /bids/{bid_id}/documents` gets OCR'd, and its extracted
fields participate in stage 4 (cross-verification) instead of the seeded placeholder JSON.

**Phase 3 — Dashboard + officer actions**
DoD: `web/` renders the bid list and bid detail views described in the guide's §10, and
`POST /bids/{bid_id}/decision` writes a verifiable audit-log entry that the frontend can display as
a chain.

**Phase 4 — Polish**
DoD: recommendation text renders on the dashboard labeled advisory-only; hash chain is visibly
verifiable (an endpoint or script that walks `audit_log` and confirms no break); all 12 seed bids
produce the `expected_ground_truth` outcome noted in `dummy_bidders.csv` when run end to end.

---

## 10. Explicit non-goals (don't build these — out of scope)

- No real government/live adapter implementations — `ADAPTER_MODE=live` can be a stub that raises
  `NotImplementedError`; the interface being ready is the point (see the guide, §5).
- No bid pricing, L1 discovery, reverse auction, or contract-award mechanics — this system stops
  at compliance verification and hands off a qualify/disqualify decision.
- No bidder-facing portal/auth flow beyond what's needed to attach documents to a `bid_id` — the
  Procurement Officer dashboard is the actual deliverable.
- No production Kubernetes manifests — `docker-compose.yml` is sufficient through Phase 4.
