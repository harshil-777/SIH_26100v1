from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Bid, Bidder, ComplianceScore, Tender
from app.schemas.dashboard import DashboardBid

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/bids", response_model=list[DashboardBid])
async def list_bids(
    tender_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[DashboardBid]:
    latest_score = (
        select(ComplianceScore)
        .distinct(ComplianceScore.bid_id)
        .order_by(ComplianceScore.bid_id, ComplianceScore.generated_at.desc())
        .subquery()
    )

    stmt = (
        select(
            Bid.bid_id,
            Bid.tender_id,
            Tender.title.label("tender_title"),
            Bid.bidder_id,
            Bidder.name.label("bidder_name"),
            Bidder.enterprise_category,
            Bid.status,
            Bid.submitted_at,
            latest_score.c.overall_score,
            latest_score.c.risk_level,
        )
        .join(Tender, Tender.tender_id == Bid.tender_id)
        .join(Bidder, Bidder.bidder_id == Bid.bidder_id)
        .outerjoin(latest_score, latest_score.c.bid_id == Bid.bid_id)
        .order_by(Bid.bid_id)
    )
    if tender_id is not None:
        stmt = stmt.where(Bid.tender_id == tender_id)

    rows = (await session.execute(stmt)).mappings().all()
    return [DashboardBid.model_validate(dict(row)) for row in rows]
