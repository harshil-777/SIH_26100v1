from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.audit import AuditVerifyOut
from app.services.audit import verify_all_chains

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify", response_model=AuditVerifyOut)
async def verify_audit_log(session: AsyncSession = Depends(get_session)) -> AuditVerifyOut:
    """Recompute every bid's hash chain across the whole audit_log and report any break."""
    result = await verify_all_chains(session)
    return AuditVerifyOut(**result, checked_at=datetime.now(timezone.utc))
