"""Stage 8: hash-chained audit_log writes, plus the chain-walk used by the audit-log endpoint.

The chain is scoped per bid_id (GET /bids/{bid_id}/audit-log is "full hash-chained history
for this bid"), so prev_hash for a new row is the curr_hash of that same bid's most recent
row, or None (serialized as "") if this is the bid's first audit entry.
"""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Bid


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
    # Lock the bid row until this transaction ends, so two writers for one bid (an officer's
    # decision landing while a verification run finishes) can't both read the same prev_hash
    # and fork the chain -- which verify_chain would then report as permanently broken.
    await session.execute(select(Bid.bid_id).where(Bid.bid_id == bid_id).with_for_update())
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


def find_breaks(rows: list[AuditLog]) -> list[dict]:
    """Walk one bid's rows in log_id order; return each break as {log_id, problem}.

    Two independent checks per row: its prev_hash must be the previous row's curr_hash (catches
    a deleted, inserted or reordered row), and its curr_hash must recompute from its own
    prev_hash + payload (catches an edited payload). Deleting the newest rows, or a bid's whole
    chain, leaves nothing to compare against and is not detectable from the table alone.
    """
    breaks: list[dict] = []
    expected_prev: str | None = None
    for row in rows:
        if (row.prev_hash or None) != expected_prev:
            breaks.append({"log_id": row.log_id, "problem": "prev_hash does not match the previous entry's hash"})
        if compute_curr_hash(row.prev_hash, row.payload_json or {}) != row.curr_hash:
            breaks.append({"log_id": row.log_id, "problem": "curr_hash does not match this entry's payload"})
        expected_prev = row.curr_hash
    return breaks


def verify_chain(rows: list[AuditLog]) -> tuple[bool, list[str]]:
    """Per-bid verdict for GET /bids/{bid_id}/audit-log: (valid, log_ids of broken entries)."""
    broken_ids = list(dict.fromkeys(str(b["log_id"]) for b in find_breaks(rows)))
    return (not broken_ids, broken_ids)


async def verify_all_chains(session: AsyncSession) -> dict:
    """Walk the whole audit_log, one chain per bid, and report every break found."""
    rows = (
        await session.execute(select(AuditLog).order_by(AuditLog.bid_id, AuditLog.log_id))
    ).scalars().all()
    chains: dict[str | None, list[AuditLog]] = {}
    for row in rows:
        chains.setdefault(row.bid_id, []).append(row)

    breaks = [
        {"bid_id": bid_id, **found}
        for bid_id, chain in chains.items()
        for found in find_breaks(chain)
    ]
    return {
        "valid": not breaks,
        "chains_checked": len(chains),
        "entries_checked": len(rows),
        "breaks": breaks,
    }
