"""The per-bid pipeline (BUILD_SPEC.md section 7), run in this exact order.

Each stage persists before the next starts. Stages 1, 4 and 5 are pure, cheap
recomputation over already-persisted facts (bid_document_submissions vs.
tender_document_requirements, declarations, verification_results), so a crash before stage
6 loses nothing: rerunning the pipeline recomputes them fresh rather than needing a
dedicated resume checkpoint. Stages 2 (documents.ocr_extracted_json) and 3
(verification_results) are the two stages with real persisted state, each committed on
completion; a rerun skips OCR for documents already extracted. Stage 6 (compliance_scores)
and 8 (audit_log) are the pipeline's durable outputs.
"""
import asyncio
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import Bid, Tender
from app.services import ml_models, ocr
from app.services.completeness import check_completeness
from app.services.audit import write_audit_log
from app.services.recommendation import recommend
from app.services.rule_engine import evaluate_criteria, gather_facts
from app.services.scoring import build_compliance_score
from app.services.verification import run_verification_stage


class BidNotFound(Exception):
    pass


async def _load_bid_and_tender(session: AsyncSession, bid_id: str) -> tuple[Bid, Tender]:
    bid = (await session.execute(select(Bid).where(Bid.bid_id == bid_id))).scalar_one_or_none()
    if bid is None:
        raise BidNotFound(bid_id)
    tender = (
        await session.execute(select(Tender).where(Tender.tender_id == bid.tender_id))
    ).scalar_one()
    return bid, tender


class _StageClock:
    """Wall-clock milliseconds per stage, returned with the result so a slow deploy can be
    diagnosed from the API response rather than guessed at."""

    def __init__(self) -> None:
        self._last = time.perf_counter()
        self.ms: dict[str, int] = {}

    def lap(self, stage: str) -> None:
        now = time.perf_counter()
        self.ms[stage] = round((now - self._last) * 1000)
        self._last = now


async def run_pipeline(session: AsyncSession, bid: Bid, tender: Tender) -> dict:
    """Runs all 8 stages against the given session and returns a JSON-safe summary."""
    clock = _StageClock()
    # Stage 1: completeness check
    completeness = await check_completeness(session, tender.tender_id, bid.bid_id)
    clock.lap("completeness")

    # Stage 2: OCR / extraction of real uploads (seeded placeholders stay a no-op), committed
    # so a crash later doesn't throw away slow OCR work.
    ocr_facts = await ocr.run_ocr_stage(session, bid.bid_id)
    await session.commit()
    clock.lap("ocr")

    # Stage 3: portal verification, in parallel, persisted to verification_results.
    # Committed here (not just flushed) so these rows genuinely survive a crash in a
    # later stage -- this is the resumability the module docstring describes.
    portal_facts = await run_verification_stage(session, bid.bid_id, bid.bidder_id)
    await session.commit()
    clock.lap("portal_checks")

    # Stage 4: cross-verification facts + Stage 5: rule engine
    facts = await gather_facts(
        session,
        bid_id=bid.bid_id,
        tender_id=tender.tender_id,
        bidder_id=bid.bidder_id,
        completeness=completeness,
        portal_facts=portal_facts,
        ocr_facts=ocr_facts,
    )
    outcomes = evaluate_criteria(tender.eligibility_rules_json or {"criteria": []}, facts)
    clock.lap("cross_check_and_rules")

    # Stage 6: scoring
    score_row = build_compliance_score(bid.bid_id, outcomes)
    # Advisory only, attached to the persisted breakdown but never read by scoring.py --
    # it cannot change overall_score or risk_level. None (the ordinary case when
    # ML_MODELS_ENABLED is unset) simply omits the key.
    # asyncio.to_thread: risk_estimate does real CPU work (model load on first call, LightGBM
    # inference after) -- run synchronously in this coroutine it would block the whole event
    # loop (single Uvicorn worker, no --workers), freezing every other in-flight request,
    # including unrelated ones like /health, for however long it takes.
    ml_risk = await asyncio.to_thread(ml_models.risk_estimate, tender, facts)
    if ml_risk is not None:
        score_row.criterion_breakdown_json["ml_risk_estimate"] = ml_risk
    session.add(score_row)
    await session.flush()
    clock.lap("scoring_and_ml_risk")

    # Stage 7: recommendation (display-only, never persisted). Same asyncio.to_thread reason
    # as above -- this one's worse in practice, since it's a flan-t5-small generate() call
    # (or a full model load + download on the very first call), the slowest single step here.
    recommendation_result = await asyncio.to_thread(
        recommend, score_row.overall_score, score_row.risk_level, score_row.criterion_breakdown_json
    )
    recommendation = recommendation_result["text"]
    clock.lap("recommendation")

    # Stage 8: audit write
    audit_payload = {
        "overall_score": float(score_row.overall_score),
        "risk_level": score_row.risk_level,
        "mandatory_failure_reasons": score_row.criterion_breakdown_json.get(
            "mandatory_failure_reasons", []
        ),
        "recommendation_source": recommendation_result["source"],
    }
    await write_audit_log(
        session, bid_id=bid.bid_id, actor="system:orchestrator", action="verify_completed", payload=audit_payload
    )

    await session.commit()
    clock.lap("audit_write")

    return {
        "bid_id": bid.bid_id,
        "overall_score": float(score_row.overall_score),
        "risk_level": score_row.risk_level,
        "mandatory_failure_reasons": audit_payload["mandatory_failure_reasons"],
        "recommendation": recommendation,
        "recommendation_source": recommendation_result["source"],
        "ml_risk_estimate": ml_risk,
        "stage_timings_ms": clock.ms,
    }


async def run_pipeline_standalone(bid_id: str) -> dict:
    """Entry point for the Celery task: opens and owns its own session/transaction."""
    async with SessionLocal() as session:
        # Not wrapped in try/except: if the bid_id itself is bad, there is no valid FK
        # target for a verify_failed audit row, so this must propagate as a bare error.
        bid, tender = await _load_bid_and_tender(session, bid_id)

        try:
            return await run_pipeline(session, bid, tender)
        except Exception as exc:
            await session.rollback()
            async with SessionLocal() as failure_session:
                await write_audit_log(
                    failure_session,
                    bid_id=bid_id,
                    actor="system:orchestrator",
                    action="verify_failed",
                    payload={"error": str(exc)},
                )
                await failure_session.commit()
            raise
