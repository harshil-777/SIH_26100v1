from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_readonly_session
from app.models import AuditLog, Bid, Bidder, Tender
from app.schemas.audit import AuditVerifyOut, RecentAuditEntry, TenderAuditSummary
from app.services.audit import verify_all_chains

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify", response_model=AuditVerifyOut)
async def verify_audit_log(session: AsyncSession = Depends(get_readonly_session)) -> AuditVerifyOut:
    """Recompute every bid's hash chain across the whole audit_log and report any break."""
    result = await verify_all_chains(session)
    # Attach each break's tender, so the audit view can show integrity per tender.
    bid_ids = {b["bid_id"] for b in result["breaks"] if b.get("bid_id")}
    tender_of = dict((await session.execute(select(Bid.bid_id, Bid.tender_id).where(Bid.bid_id.in_(bid_ids)))).all()) if bid_ids else {}
    breaks = [{**b, "tender_id": tender_of.get(b.get("bid_id"))} for b in result["breaks"]]
    return AuditVerifyOut(**{**result, "breaks": breaks}, checked_at=datetime.now(timezone.utc))


@router.get("/tenders", response_model=list[TenderAuditSummary])
async def audit_by_tender(session: AsyncSession = Depends(get_readonly_session)) -> list[TenderAuditSummary]:
    """Audit activity rolled up per tender: how many verifications and decisions it has seen."""
    stmt = (
        select(
            Tender.tender_id,
            Tender.title,
            Tender.department,
            func.count(func.distinct(Bid.bid_id)).label("bid_count"),
            func.count(AuditLog.log_id).label("entry_count"),
            func.count(AuditLog.log_id).filter(AuditLog.action == "verify_completed").label("verification_count"),
            func.count(AuditLog.log_id).filter(AuditLog.action == "officer_decision").label("decision_count"),
            func.max(AuditLog.timestamp).label("last_activity_at"),
        )
        .outerjoin(Bid, Bid.tender_id == Tender.tender_id)
        .outerjoin(AuditLog, AuditLog.bid_id == Bid.bid_id)
        .group_by(Tender.tender_id)
        .order_by(func.max(AuditLog.timestamp).desc().nulls_last(), Tender.tender_id)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [TenderAuditSummary.model_validate(dict(row)) for row in rows]


@router.get("/recent", response_model=list[RecentAuditEntry])
async def recent_activity(
    limit: int = Query(20, ge=1, le=1000),
    tender_id: str | None = None,
    session: AsyncSession = Depends(get_readonly_session),
) -> list[RecentAuditEntry]:
    """Newest audit entries across every bid, or across one tender's bids."""
    stmt = (
        select(
            AuditLog.log_id,
            AuditLog.bid_id,
            Bidder.name.label("bidder_name"),
            Bid.tender_id,
            AuditLog.actor,
            AuditLog.action,
            AuditLog.payload_json,
            AuditLog.timestamp,
        )
        .outerjoin(Bid, Bid.bid_id == AuditLog.bid_id)
        .outerjoin(Bidder, Bidder.bidder_id == Bid.bidder_id)
        .order_by(AuditLog.timestamp.desc(), AuditLog.log_id.desc())
        .limit(limit)
    )
    if tender_id is not None:
        stmt = stmt.where(Bid.tender_id == tender_id)
    rows = (await session.execute(stmt)).mappings().all()
    return [RecentAuditEntry.model_validate(dict(row)) for row in rows]
