from datetime import datetime

from pydantic import BaseModel


class ChainBreakOut(BaseModel):
    bid_id: str | None
    log_id: int
    problem: str


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
