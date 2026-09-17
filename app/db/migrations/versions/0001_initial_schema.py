"""Initial schema (BUILD_SPEC.md section 3)

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_DDL = """
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
    source TEXT NOT NULL,
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
"""

DROP_ORDER = [
    "audit_log",
    "debarred_entities",
    "compliance_scores",
    "verification_results",
    "documents",
    "bid_declarations",
    "bid_document_submissions",
    "tender_document_requirements",
    "document_types",
    "bids",
    "bidders",
    "tenders",
    "users",
]


def upgrade() -> None:
    # asyncpg's prepared-statement protocol rejects multiple commands in a single
    # execute() call, so the DDL block must be split and run one statement at a time.
    for statement in SCHEMA_DDL.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement + ";")


def downgrade() -> None:
    for table in DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
