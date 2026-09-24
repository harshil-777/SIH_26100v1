"""Phase 4's DoD from a clean seed: every seed bid, through the full 8-stage pipeline, matches the
expected_ground_truth in dummy_bidders.csv. Runs the orchestrator directly, so no Celery/Redis."""
import pytest
from sqlalchemy import func, select

from app.db.ground_truth import EXPECTATIONS, evaluate
from app.db.session import SessionLocal
from app.models import AuditLog, ComplianceScore
from app.services.orchestrator import run_pipeline_standalone
from app.services.recommendation import generate_recommendation

SEED_BID_IDS = [
    "BID-B001-T2026-0001", "BID-B002-T2026-0003", "BID-B003-T2026-0002", "BID-B004-T2026-0001",
    "BID-B005-T2026-0003", "BID-B006-T2026-0005", "BID-B007-T2026-0004", "BID-B008-T2026-0004",
    "BID-B009-T2026-0006", "BID-B010-T2026-0003", "BID-B011-T2026-0004", "BID-B012-T2026-0001",
]


def test_every_seed_scenario_has_an_expectation(seed_bids):
    assert [b["bid_id"] for b in seed_bids] == SEED_BID_IDS
    assert {b["scenario_tag"] for b in seed_bids} == EXPECTATIONS.keys()


@pytest.mark.parametrize("bid_id", SEED_BID_IDS)
async def test_seed_bid_matches_expected_ground_truth(seeded_db, seed_bids, bid_id):
    bid = next(b for b in seed_bids if b["bid_id"] == bid_id)
    summary = await run_pipeline_standalone(bid_id)

    async with SessionLocal() as session:
        score = (
            await session.execute(
                select(ComplianceScore).where(ComplianceScore.bid_id == bid_id).order_by(ComplianceScore.generated_at.desc()).limit(1)
            )
        ).scalar_one()
        audit_rows = await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.bid_id == bid_id))

    recommendation = generate_recommendation(score.overall_score, score.risk_level, score.criterion_breakdown_json)
    problems = evaluate(bid["scenario_tag"], score.risk_level, score.criterion_breakdown_json, recommendation)
    assert not problems, f"{bid['scenario_tag']}: {problems} (expected: {bid['expected_ground_truth']})"

    assert summary["risk_level"] == score.risk_level
    assert audit_rows >= 1  # stage 8 wrote the run to the audit log
