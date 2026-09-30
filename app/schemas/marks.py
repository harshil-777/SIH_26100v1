from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarkIn(BaseModel):
    marked_by: str = Field(min_length=1)
    note: str | None = None


class MarkOut(BaseModel):
    bid_id: str
    marked_by: str
    note: str | None
    marked_at: datetime

    model_config = {"from_attributes": True}


class MarkedBidOut(BaseModel):
    bid_id: str
    tender_id: str
    tender_title: str
    bidder_name: str
    enterprise_category: str | None
    status: str
    overall_score: Decimal | None
    risk_level: str | None
    marked_by: str
    note: str | None
    marked_at: datetime
