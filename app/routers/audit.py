from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import AuditLog, Bid, Bidder
from app.schemas.audit import AuditVerifyOut, RecentAuditEntry
from app.services.audit import verify_all_chains

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify", response_model=AuditVerifyOut)
async def verify_audit_log(session: AsyncSession = Depends(get_session)) -> AuditVerifyOut:
    """Recompute every bid's hash chain across the whole audit_log and report any break."""
    result = await verify_all_chains(session)
    return AuditVerifyOut(**result, checked_at=datetime.now(timezone.utc))


@router.get("/recent", response_model=list[RecentAuditEntry])
async def recent_activity(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecentAuditEntry]:
    """Newest audit entries across every bid -- the per-bid endpoint only shows one chain."""
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
    rows = (await session.execute(stmt)).mappings().all()
    return [RecentAuditEntry.model_validate(dict(row)) for row in rows]
