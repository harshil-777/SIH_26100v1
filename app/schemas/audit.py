from datetime import datetime

from pydantic import BaseModel


class ChainBreakOut(BaseModel):
    bid_id: str | None
    tender_id: str | None = None
    log_id: int
    problem: str


class TenderAuditSummary(BaseModel):
    tender_id: str
    title: str
    department: str
    bid_count: int
    entry_count: int
    verification_count: int
    decision_count: int
    last_activity_at: datetime | None


class RecentAuditEntry(BaseModel):
    log_id: int
    bid_id: str | None
    bidder_name: str | None
    tender_id: str | None
    actor: str
    action: str
    payload_json: dict | None
    timestamp: datetime


class AuditVerifyOut(BaseModel):
    valid: bool
    chains_checked: int
    entries_checked: int
    breaks: list[ChainBreakOut]
    checked_at: datetime
