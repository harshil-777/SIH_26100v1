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
- **OCR**: `pdfplumber` reads a PDF's own text layer; `pytesseract` + the Tesseract binary handle
  images and scanned PDFs (Phase 2). Tesseract is a system dependency, not a pip package — the
  Docker image installs it (`tesseract-ocr`). Settings, all optional: `TESSERACT_CMD` (path, only
  if not on `PATH`), `MAX_UPLOAD_MB` (default 10), `OCR_MAX_PAGES` (default 5).
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
    ocr.py                # document extraction: text layer / Tesseract + field parsing (§7 stage 2)
    object_store.py       # ObjectStore interface + LocalObjectStore (§5)
    recommendation.py     # LLM call, structured input only
  /db
    seed.py             # loads the six seed files into Postgres
    migrations/          # alembic
  main.py
/scripts
  make_sample_documents.py  # generates sample certificates for exercising uploads + OCR
  check_ground_truth.py     # runs all 12 seed bids end to end, checks expected_ground_truth (Phase 4)
  verify_audit_chain.py     # walks the whole audit_log straight from the DB, confirms no break (Phase 4)
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

Uploaded files go through one storage interface, so nothing outside it knows they live on local
disk (Phase 2):

```python
# app/services/object_store.py
class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...

def get_object_store() -> ObjectStore: ...   # LocalObjectStore(STORAGE_DIR) today
```

Keys are opaque strings. `LocalObjectStore` must reject any key that resolves outside its root and
write atomically (temp file, then rename). Uploads use content-addressed keys,
`documents/<sha256><ext>`, so no client-supplied filename ever reaches the filesystem.

---

## 6. API endpoints (Phase 1 minimum set, plus Phase 2 uploads)

| Method | Path | Purpose |
|---|---|---|
| POST | `/tenders` | Create a tender |
| GET | `/tenders/{tender_id}` | Tender detail |
| GET | `/tenders/{tender_id}/document-requirements` | List `tender_document_requirements` for it |
| POST | `/bids` | Create a bid (bidder + tender) |
| GET | `/bids/{bid_id}` | Bid detail for the dashboard: bidder, tender, declarations, and the latest `verification_results` row per source (Phase 3) |
| POST | `/bids/{bid_id}/documents` | Multipart upload of one document (Phase 2 — replaces Phase 1's JSON file-reference form). Details below |
| GET | `/bids/{bid_id}/documents` | Each submission with its latest upload and OCR result; `is_placeholder` marks seeded rows with no stored file |
| POST | `/bids/{bid_id}/declarations` | Submit/update `bid_declarations` rows |
| POST | `/bids/{bid_id}/verify` | Enqueue the orchestrator pipeline (§7) as a Celery task; returns immediately with a job id |
| GET | `/bids/{bid_id}/status` | Poll job/pipeline status |
| GET | `/bids/{bid_id}/compliance-score` | Latest `compliance_scores` row + `criterion_breakdown_json` |
| GET | `/bids/{bid_id}/audit-log` | Full hash-chained history for this bid |
| POST | `/bids/{bid_id}/decision` | Officer action: `qualify` / `disqualify` / `request_clarification`; writes to `audit_log`. `actor` is required; `reason` is required for `disqualify` and `request_clarification` (422 otherwise). The hashed payload carries `decision`, `reason`, `actor`, `previous_status` and `new_status` |
| GET | `/dashboard/bids?tender_id=` | List view: bid, bidder, score, risk badge, status |
| GET | `/audit/verify` | Recompute every bid's hash chain across the whole `audit_log`; returns `valid`, counts, and each break as `{bid_id, log_id, problem}` (Phase 4) |

**`POST /bids/{bid_id}/documents` contract.** Form fields: `document_type` (a `document_types`
code), `file` (optional), `note` (optional). Omitting `file` records an explicit non-submission
(`submitted = FALSE`), which overrides any earlier upload of that type. Uploading again for the
same `document_type` replaces the bid's submission (one `bid_document_submissions` row per bid +
type); every upload is kept as its own `documents` row and only the latest counts.

- The file type is decided from the leading bytes (PDF, PNG, JPEG, TIFF), never from the
  client's content-type or filename.
- The file is written to the `ObjectStore` before the DB commit, so no row ever references a
  missing file. `file_ref` and `documents.file_url` hold the store key; `documents.file_hash`
  holds the SHA-256.
- Errors: `404` unknown bid, `422` unknown `document_type`, `400` empty file, `415` unsupported
  type, `413` over `MAX_UPLOAD_MB`.
- `201` returns `ocr_status`: `queued` (an `ocr_document` Celery task was enqueued),
  `pending_verification` (broker unreachable — the upload still succeeded and OCR runs in stage 2
  of the next `/verify`), or `not_applicable` (no file).
- Enqueueing must never hang a request when Redis is down: publishing uses a bounded connection
  attempt, and `POST /bids/{bid_id}/verify` answers `503` instead of blocking.

---

## 7. Orchestrator pipeline (`app/services/orchestrator.py`)

Run in this exact order per bid; each stage's output feeds the next and is persisted before moving
on (so a crash mid-pipeline can resume, not restart):

1. **Completeness check** — diff `bid_document_submissions` (mandatory=TRUE rows only) against
   `tender_document_requirements` for this bid's tender. Missing mandatory items → immediate
   mandatory-failure flags, still continue the pipeline (the officer should see everything, not
   just the first failure).
2. **OCR / extraction** — for each doc_type the bid currently marks `submitted=TRUE`, take its
   latest `documents` row and run `services/ocr.py`, writing the result to
   `documents.ocr_extracted_json`. Seeded placeholder rows (no stored file behind `file_url`) are
   skipped, so seed-only bids are unaffected. Committed on completion (slow work must survive a
   later crash), and skipped on rerun for a document whose `file_hash` already has a result.
   - Text comes from the PDF text layer when it has at least ~20 non-whitespace characters, else
     each page (up to `OCR_MAX_PAGES`) is rasterised at 300 dpi and OCR'd; images always use
     Tesseract.
   - Extraction never raises. The stored JSON carries `status` (`extracted` | `no_text` |
     `failed` | `ocr_unavailable`), `method` (`pdf_text_layer` | `tesseract` | `pdf_tesseract`),
     `fields`, `file_hash`, `page_count`, `pages_processed`, `char_count`, `text_excerpt` (first
     1,500 characters) and `error` when relevant. `ocr_unavailable` (Tesseract not installed) is
     retried on the next run; the other statuses are final for that file.
   - `fields` holds whichever of these were found: `gstin`, `pan`, `udyam_number`, `cin`,
     `establishment_code`, `dpiit_number`, `trade_name`, `legal_name`, `activity`,
     `enterprise_category`, `local_content_pct`, `valid_until`. A "minimum local content of N%"
     threshold restated in a certificate is not read as the certified figure.
3. **Portal verification** — call every adapter in parallel (`asyncio.gather`, not sequential
   awaits) via `get_adapter(source).verify(bidder_id)`, persist each to `verification_results`.
4. **Three-way cross-verification** — for every criterion with more than one of
   {declaration, document, portal} available, compare. Persist per-criterion match/mismatch to
   `criterion_breakdown_json` (not a separate table — it's an artifact of this bid's scoring run).
   - The comparisons are per fact, and each compares every pair among whichever sources exist:
     enterprise category, local-content % (±2 points), startup recognition, manufacturer vs.
     trader, GSTIN, GST trade name, GST legal name, PAN, Udyam number, EPFO establishment code,
     DPIIT number. Names are compared as normalised token sets (legal suffixes such as
     "Pvt Ltd" ignored), so a genuinely different trade name is a mismatch but formatting is not.
   - The document leg is the real `fields` from stage 2. The seed fixture's pre-computed
     `document_cross_check` array is only a placeholder for document types with no upload yet;
     once a real upload of the corresponding type exists it is superseded and dropped (listed
     under `superseded_placeholders` in the evidence).
   - A document stage 2 could not read (`failed`, `no_text`, `ocr_unavailable`) is reported under
     `unreadable_documents` and named in the criterion's reason, but does not lower the score —
     an unreadable file is not evidence that the bidder's claim is false.
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

Beyond this example, `build_eligibility_rules_typed` (`app/db/fixtures.py`) adds
`declaration_document_consistency` (graded, 0.25) to every tender, and
`{"id": "msme_eligibility", "type": "mandatory"}` to MSME-reserved tenders (Phase 4; migration
`0002` rewrote the stored configs, which had it as graded). A reservation bars non-MSME bidders
outright, so ineligibility must disqualify with that reason rather than lower a weighted score.
The evaluator still honours a `graded` `msme_eligibility` if a tender's config says so.

`document_completeness` does not count a missing `EMD_EXEMPTION_PROOF` as a gap when the portals
show the bidder is neither an MSE (valid Udyam, Micro/Small/Medium) nor a recognized startup: such
a bidder cannot produce that proof, so its absence is a symptom of ineligibility (handled by
`msme_eligibility` on reserved tenders), not a paperwork gap. It is listed under
`not_applicable_documents` in the criterion's evidence with the reason.

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

**Phase 2 — Real uploads + OCR** — ✅ complete
DoD: a real PDF/image upload through `POST /bids/{bid_id}/documents` gets OCR'd, and its extracted
fields participate in stage 4 (cross-verification) instead of the seeded placeholder JSON.

Verified against the live database:
- A text-layer PDF, a PNG and an image-only (scanned) PDF all extract correctly.
- `BID-B009-T2026-0006`: uploading a GST certificate whose trade name differs from the GSTN record
  replaces the fixture placeholder and the mismatch is detected from the document itself; a
  matching certificate takes the bid from 28.57 / High to 100 / Low.
- `BID-B006-T2026-0005`: an MII certificate stating 40% yields the declared 45 / document 40 /
  portal 38 discrepancy from real extracted values.
- With no real uploads, all 12 seed bids score identically to Phase 1.
- Every validation error above, corrupt files, and a later non-submission overriding an earlier
  upload behave as specified.

Known limits: extraction is regex-based over free text, so a certificate whose labels differ
from the common government layouts may yield fewer fields (the field is then simply absent, never
guessed); only the first `OCR_MAX_PAGES` pages are read; `ocr_document` tasks and `/verify` both
need Redis, and image OCR needs the Tesseract binary (see §1).

**Phase 3 — Dashboard + officer actions** — ✅ complete
DoD: `web/` renders the bid list and bid detail views described in the guide's §10, and
`POST /bids/{bid_id}/decision` writes a verifiable audit-log entry that the frontend can display as
a chain.

Built (the guide was not in this drop, so the views follow this spec and the API):
- **Bid list** (`#/`): risk-band count tiles that double as filters, tender / status filters,
  search, score sort; a card layout below the `md` breakpoint.
- **Bid detail** (`#/bids/<bid_id>`): score gauge + mandatory failures + the advisory
  recommendation (labelled AI-generated, advisory only); criteria breakdown with normalised
  weights; three-way cross-verification table (declared / document / portal, mismatched legs in
  red, seed placeholders and unreadable uploads called out); documents with OCR status and
  extracted fields; latest portal checks; bidder & tender profile with self-declarations; a
  "Re-run verification" button that polls `/status`.
- **Decision panel**: qualify / request clarification / disqualify, officer name, reason
  (required for adverse decisions, and in the UI also when qualifying a High / Non-Compliant
  bid). On submit the status and audit trail refresh in place.
- **Audit trail**: newest-first chain, each entry showing `prev_hash → curr_hash`, a per-link
  check that `prev_hash` equals the preceding `curr_hash`, and the server's `chain_valid` /
  `broken_at` verdict.

Verified in a browser against the live database: all 12 bids list with correct scores and bands;
B009 shows the GST trade-name mismatch from the real upload; B012 shows the missing OEM letter as
the mandatory failure; disqualifying B002 is blocked until a reason is entered, then appends a
linked entry and the chain stays intact; no horizontal scroll at 390px.

**Phase 4 — Polish** — ✅ complete
DoD: recommendation text renders on the dashboard labeled advisory-only; hash chain is visibly
verifiable (an endpoint or script that walks `audit_log` and confirms no break); all 12 seed bids
produce the `expected_ground_truth` outcome noted in `dummy_bidders.csv` when run end to end.

- **Recommendation**: rendered on the bid detail page in a panel labelled "AI-generated · advisory
  only", separate from the officer's decision. The text now uses readable criterion and fact names
  (not raw ids such as `declaration_document_consistency`). It is still the deterministic
  template in `services/recommendation.py`; no LLM is wired in (see Known limits).
- **Hash chain**: `services/audit.py` walks each bid's chain in `log_id` order and checks two things
  per entry: `prev_hash` equals the previous entry's `curr_hash` (catches a deleted, inserted or
  reordered entry) and `curr_hash` recomputes from its own `prev_hash` + payload (catches an edited
  payload). Exposed three ways: `GET /audit/verify` (whole log), `scripts/verify_audit_chain.py`
  (reads the DB directly, exits 1 on a break), and an "Audit log intact / tampering detected" panel
  on the dashboard's bid list that re-checks on demand and links to any broken bid. Writes are
  serialised per bid (the bid row is locked while the next entry is appended), so concurrent
  writers can't fork a chain.
- **Ground truth**: `scripts/check_ground_truth.py` re-verifies all 12 seed bids through the API
  and checks each against its scenario, with `expected_ground_truth`'s free text pinned down as
  explicit checks — the risk band, which mandatory criterion must be the one that fails (so a bid
  can't pass for the wrong reason), and which flag must be raised. Result: **12/12**.
  The one fix it needed was B010 (`not_msme_ineligible_for_reservation`): it was disqualified for
  a "missing document", while its fixture says statutory checks pass and it is ineligible only on
  the tender's MSME reservation — see §8 for the rule change.

Verified against the live database: 12/12 ground-truth run end to end; `/audit/verify` and the
script both report 12 intact chains; editing an entry's payload and deleting a mid-chain entry
(inside a rolled-back transaction) were each detected at the right `log_id`; the dashboard shows
the intact and the broken state (the latter simulated in the browser), B010's new reason, and its
exemption proof as "Not applicable" rather than "Missing".

Known limits:
- The chain proves integrity *within* what is stored. Deleting a bid's newest entries, or its
  whole chain, leaves nothing to compare against; detecting that needs the latest hash anchored
  outside the database (e.g. periodically published or signed).
- `actor`, `action` and `timestamp` are columns outside the hashed payload. Officer decisions
  copy `actor` into the payload (Phase 3), so it is covered for them, not for orchestrator rows.
- The recommendation is a deterministic template. §7 stage 7 envisages an LLM over the structured
  breakdown; that needs an API key and, per §1, must run inside the Celery task with its output
  stored for display (it is currently computed per request).

---

## 10. Explicit non-goals (don't build these — out of scope)

- No real government/live adapter implementations — `ADAPTER_MODE=live` can be a stub that raises
  `NotImplementedError`; the interface being ready is the point (see the guide, §5).
- No bid pricing, L1 discovery, reverse auction, or contract-award mechanics — this system stops
  at compliance verification and hands off a qualify/disqualify decision.
- No bidder-facing portal/auth flow beyond what's needed to attach documents to a `bid_id` — the
  Procurement Officer dashboard is the actual deliverable.
- No production Kubernetes manifests — `docker-compose.yml` is sufficient through Phase 4.
- No cloud OCR service (Google Vision, Textract, ...) — Tesseract only. No document-forgery
  detection or virus scanning of uploads; a name/number mismatch against the portal is the only
  authenticity signal the system produces.
