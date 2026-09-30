from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Bid, Bidder, BidMark, ComplianceScore, Tender
from app.schemas.marks import MarkedBidOut, MarkIn, MarkOut

router = APIRouter(tags=["marks"])


@router.get("/marks", response_model=list[MarkedBidOut])
async def list_marked_bids(session: AsyncSession = Depends(get_session)) -> list[MarkedBidOut]:
    """Every bid an officer has flagged to check later, newest mark first."""
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
            Bidder.name.label("bidder_name"),
            Bidder.enterprise_category,
            Bid.status,
            latest_score.c.overall_score,
            latest_score.c.risk_level,
            BidMark.marked_by,
            BidMark.note,
            BidMark.marked_at,
        )
        .join(Bid, Bid.bid_id == BidMark.bid_id)
        .join(Tender, Tender.tender_id == Bid.tender_id)
        .join(Bidder, Bidder.bidder_id == Bid.bidder_id)
        .outerjoin(latest_score, latest_score.c.bid_id == Bid.bid_id)
        .order_by(BidMark.marked_at.desc())
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [MarkedBidOut.model_validate(dict(row)) for row in rows]


@router.put("/bids/{bid_id}/mark", response_model=MarkOut)
async def mark_bid(bid_id: str, payload: MarkIn, session: AsyncSession = Depends(get_session)) -> MarkOut:
    if await session.get(Bid, bid_id) is None:
        raise HTTPException(404, f"Bid {bid_id!r} not found")
    values = {"bid_id": bid_id, "marked_by": payload.marked_by.strip(), "note": (payload.note or "").strip() or None}
    stmt = (
        insert(BidMark)
        .values(**values)
        .on_conflict_do_update(index_elements=[BidMark.bid_id], set_={"marked_by": values["marked_by"], "note": values["note"]})
        .returning(BidMark)
    )
    mark = (await session.execute(stmt)).scalar_one()
    await session.commit()
    return MarkOut.model_validate(mark)


@router.delete("/bids/{bid_id}/mark", status_code=204)
async def unmark_bid(bid_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    await session.execute(delete(BidMark).where(BidMark.bid_id == bid_id))
    await session.commit()
    return Response(status_code=204)
