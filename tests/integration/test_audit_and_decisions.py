"""Officer decisions through the API, and the audit chain's integrity guarantees, on a real DB."""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app.db.session import SessionLocal
from app.main import app
from app.models import AuditLog, Bid
from app.services.audit import verify_all_chains, write_audit_log
from app.services.orchestrator import run_pipeline_standalone

BID = "BID-B002-T2026-0003"


@pytest.fixture(scope="module")
def client(seeded_db):
    return TestClient(app)


async def test_decision_updates_status_and_appends_a_hashed_entry_naming_the_officer(client):
    await run_pipeline_standalone(BID)
    response = client.post(
        f"/bids/{BID}/decision",
        json={"decision": "disqualify", "actor": "officer@example.gov.in", "reason": "GSTIN cancelled"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "disqualified"

    log = client.get(f"/bids/{BID}/audit-log").json()
    assert log["chain_valid"] is True
    latest = log["entries"][-1]
    assert latest["action"] == "officer_decision"
    assert latest["prev_hash"] == log["entries"][-2]["curr_hash"]
    # Who decided and the status transition are inside the hashed payload, not just columns.
    assert latest["payload_json"] == {
        "decision": "disqualify",
        "reason": "GSTIN cancelled",
        "actor": "officer@example.gov.in",
        "previous_status": "submitted",
        "new_status": "disqualified",
    }


def test_decision_on_unknown_bid_is_404(client):
    response = client.post("/bids/BID-NOPE/decision", json={"decision": "qualify", "actor": "o"})
    assert response.status_code == 404


async def test_concurrent_writers_for_one_bid_are_serialised_so_the_chain_cannot_fork(seeded_db):
    first, second = SessionLocal(), SessionLocal()
    try:
        row_a = await write_audit_log(first, bid_id=BID, actor="test-a", action="test", payload={"n": "a"})
        # While `first` holds its transaction open, a second writer for the same bid must wait
        # instead of reading the same prev_hash.
        pending_b = asyncio.create_task(write_audit_log(second, bid_id=BID, actor="test-b", action="test", payload={"n": "b"}))
        await asyncio.sleep(1)
        assert not pending_b.done(), "second writer did not wait for the first -> chain would fork"
        await first.commit()
        row_b = await asyncio.wait_for(pending_b, timeout=10)
        await second.commit()
        assert row_b.prev_hash == row_a.curr_hash
    finally:
        await first.close()
        await second.close()

    async with SessionLocal() as session:
        assert (await verify_all_chains(session))["valid"] is True


async def test_whole_log_walk_catches_edits_and_deletions(seeded_db):
    async with SessionLocal() as session:
        await run_pipeline_standalone(BID)  # ensure the chain has enough entries
        rows = (await session.execute(select(AuditLog).where(AuditLog.bid_id == BID).order_by(AuditLog.log_id))).scalars().all()
        assert len(rows) >= 4
        edited, deleted = rows[0], rows[2]
        await session.execute(update(AuditLog).where(AuditLog.log_id == edited.log_id).values(payload_json={"tampered": True}))
        await session.execute(delete(AuditLog).where(AuditLog.log_id == deleted.log_id))
        session.expire_all()

        result = await verify_all_chains(session)
        found = {(b["log_id"], b["problem"]) for b in result["breaks"]}
        assert (edited.log_id, "curr_hash does not match this entry's payload") in found
        assert (rows[3].log_id, "prev_hash does not match the previous entry's hash") in found
        assert result["valid"] is False
        await session.rollback()


def test_audit_verify_endpoint_reports_every_chain(client):
    body = client.get("/audit/verify").json()
    assert body["valid"] is True
    assert body["chains_checked"] >= 1 and body["breaks"] == []


async def test_bid_status_column_matches_last_decision(seeded_db):
    async with SessionLocal() as session:
        assert (await session.get(Bid, BID)).status == "disqualified"
