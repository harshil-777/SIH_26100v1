import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


class BidCreate(BaseModel):
    tender_id: str
    bidder_id: str


class BidOut(BaseModel):
    bid_id: str
    tender_id: str
    bidder_id: str
    submitted_at: datetime
    status: str

    model_config = {"from_attributes": True}


class DocumentUploadOut(BaseModel):
    submission_id: str
    bid_id: str
    document_type: str
    submitted: bool
    file_ref: str | None
    note: str | None
    doc_id: uuid.UUID | None
    file_hash: str | None
    file_kind: str | None
    size_bytes: int | None
    # queued: OCR task enqueued now. pending_verification: broker unreachable, so OCR will
    # run in stage 2 of the next /verify instead. not_applicable: no file was uploaded.
    ocr_status: Literal["queued", "pending_verification", "not_applicable"]


class DocumentOut(BaseModel):
    document_type: str
    submitted: bool
    file_ref: str | None
    note: str | None
    doc_id: uuid.UUID | None
    file_hash: str | None
    uploaded_at: datetime | None
    # True for seeded rows whose file_ref points at no real stored file.
    is_placeholder: bool
    ocr: dict[str, Any] | None


class DeclarationIn(BaseModel):
    criterion_code: str
    declared_value: str
    note: str | None = None


class DeclarationOut(BaseModel):
    declaration_id: str
    bid_id: str
    criterion_code: str
    declared_value: str
    declared_at: datetime
    note: str | None

    model_config = {"from_attributes": True}


class VerifyJobOut(BaseModel):
    bid_id: str
    job_id: str
    status: Literal["queued"]


class StatusOut(BaseModel):
    bid_id: str
    job_status: Literal["not_started", "queued", "running", "success", "failed"]
    celery_state: str
    result: dict[str, Any] | None = None
    error: str | None = None


class ComplianceScoreOut(BaseModel):
    bid_id: str
    overall_score: Decimal
    risk_level: str
    criterion_breakdown_json: dict[str, Any]
    generated_at: datetime
    recommendation: str


class DecisionIn(BaseModel):
    decision: Literal["qualify", "disqualify", "request_clarification"]
    actor: str
    reason: str | None = None


class DecisionOut(BaseModel):
    bid_id: str
    status: str
    audit_log_id: int


class AuditLogEntryOut(BaseModel):
    log_id: int
    bid_id: str | None
    actor: str
    action: str
    payload_json: dict[str, Any] | None
    timestamp: datetime
    prev_hash: str | None
    curr_hash: str

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    bid_id: str
    chain_valid: bool
    broken_at: list[str]
    entries: list[AuditLogEntryOut]
