from datetime import datetime

from pydantic import BaseModel


class ChainBreakOut(BaseModel):
    bid_id: str | None
    log_id: int
    problem: str


class AuditVerifyOut(BaseModel):
    valid: bool
    chains_checked: int
    entries_checked: int
    breaks: list[ChainBreakOut]
    checked_at: datetime
