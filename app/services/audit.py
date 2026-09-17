"""Stage 8: hash-chained audit_log writes, plus the chain-walk used by the audit-log endpoint.

The chain is scoped per bid_id (GET /bids/{bid_id}/audit-log is "full hash-chained history
for this bid"), so prev_hash for a new row is the curr_hash of that same bid's most recent
row, or None (serialized as "") if this is the bid's first audit entry.
"""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def compute_curr_hash(prev_hash: str | None, payload: dict) -> str:
    base = (prev_hash or "") + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


async def _latest_curr_hash(session: AsyncSession, bid_id: str) -> str | None:
    return (
        await session.execute(
            select(AuditLog.curr_hash)
            .where(AuditLog.bid_id == bid_id)
            .order_by(AuditLog.log_id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def write_audit_log(
    session: AsyncSession, *, bid_id: str, actor: str, action: str, payload: dict
) -> AuditLog:
    prev_hash = await _latest_curr_hash(session, bid_id)
    curr_hash = compute_curr_hash(prev_hash, payload)
    row = AuditLog(
        bid_id=bid_id,
        actor=actor,
        action=action,
        payload_json=payload,
        prev_hash=prev_hash,
        curr_hash=curr_hash,
    )
    session.add(row)
    await session.flush()
    return row


async def get_audit_log(session: AsyncSession, bid_id: str) -> list[AuditLog]:
    return (
        await session.execute(
            select(AuditLog).where(AuditLog.bid_id == bid_id).order_by(AuditLog.log_id.asc())
        )
    ).scalars().all()


def verify_chain(rows: list[AuditLog]) -> tuple[bool, list[str]]:
    """Recomputes each curr_hash from (prev_hash, payload) and checks for breaks."""
    broken_at: list[str] = []
    expected_prev: str | None = None
    for row in rows:
        if row.prev_hash != (expected_prev or None):
            broken_at.append(row.log_id and str(row.log_id))
        recomputed = compute_curr_hash(row.prev_hash, row.payload_json or {})
        if recomputed != row.curr_hash:
            broken_at.append(str(row.log_id))
        expected_prev = row.curr_hash
    return (len(broken_at) == 0, broken_at)
