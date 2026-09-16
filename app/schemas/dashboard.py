from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DashboardBid(BaseModel):
    bid_id: str
    tender_id: str
    tender_title: str
    bidder_id: str
    bidder_name: str
    enterprise_category: str | None
    status: str
    submitted_at: datetime
    overall_score: Decimal | None
    risk_level: str | None
