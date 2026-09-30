"""Add the generated demo bids (WORKING DOCUMENTS/demo_bids, from scripts/generate_demo_bids.py)
to an already-seeded database, then score each through the real pipeline.

    python -m app.db.seed_demo            # insert missing demo bids, verify them, record decisions
    python -m app.db.seed_demo --reset    # first remove every demo (G###) bidder and all its rows

Unlike app.db.seed this never truncates: base-fixture bids, their scores and their audit history
are left exactly as they are. Only rows belonging to the demo bidder IDs are ever written or,
with --reset, deleted.
"""
import argparse
import asyncio
import json
import random
from datetime import datetime

from sqlalchemy import delete, select

from app.config import get_settings
from app.db.fixtures import as_bool, as_int, as_text, as_utc_datetime, read_csv, split_debarment_period
from app.db.session import SessionLocal
from app.models import (
    AuditLog,
    Bid,
    Bidder,
    BidDeclaration,
    BidDocumentSubmission,
    ComplianceScore,
    DebarredEntity,
    Document,
    VerificationResult,
)
from app.routers.bids import record_decision
from app.schemas.bids import DecisionIn
from app.services.orchestrator import run_pipeline_standalone

OFFICERS = ["A. Mehta (Procurement Officer)", "S. Iyer (Evaluation Committee)", "R. Khan (Technical Evaluator)"]


def _load():
    base = get_settings().seed_data_dir / "demo_bids"
    if not base.exists():
        raise SystemExit(f"{base} not found -- run scripts/generate_demo_bids.py first")
    portal = json.loads((base / "portal_responses.json").read_text(encoding="utf-8"))["bidders"]
    return (
        read_csv(base / "bidders.csv"),
        read_csv(base / "submissions.csv"),
        read_csv(base / "declarations.csv"),
        {entry["bidder_id"]: entry for entry in portal},
    )


def _bid_id(row: dict) -> str:
    return f"BID-{row['bidder_id']}-{row['target_tender_id']}"


async def reset(bidders: list[dict]) -> None:
    bidder_ids = [row["bidder_id"] for row in bidders]
    bid_ids = [_bid_id(row) for row in bidders]
    async with SessionLocal() as session:
        for model, column in (
            (AuditLog, AuditLog.bid_id),
            (ComplianceScore, ComplianceScore.bid_id),
            (VerificationResult, VerificationResult.bid_id),
            (Document, Document.bid_id),
            (BidDeclaration, BidDeclaration.bid_id),
            (BidDocumentSubmission, BidDocumentSubmission.bid_id),
            (Bid, Bid.bid_id),
        ):
            await session.execute(delete(model).where(column.in_(bid_ids)))
        await session.execute(delete(DebarredEntity).where(DebarredEntity.pan.in_([row["pan"] for row in bidders])))
        await session.execute(delete(Bidder).where(Bidder.bidder_id.in_(bidder_ids)))
        await session.commit()
    print(f"removed {len(bidder_ids)} demo bidders and their rows")


async def insert(bidders, submissions, declarations, portal) -> list[str]:
    async with SessionLocal() as session:
        existing = set((await session.execute(select(Bidder.bidder_id).where(
            Bidder.bidder_id.in_([row["bidder_id"] for row in bidders])))).scalars())
        new = [row for row in bidders if row["bidder_id"] not in existing]
        if not new:
            print("all demo bidders already present")
            return []
        new_ids = {row["bidder_id"] for row in new}

        session.add_all(
            Bidder(
                bidder_id=row["bidder_id"], name=row["name"], pan=row["pan"], gstin=as_text(row["gstin"]),
                udyam_number=as_text(row["udyam_number"]), cin=as_text(row["cin"]),
                dpiit_recognition_number=as_text(row["dpiit_recognition_number"]),
                nsic_registration_number=as_text(row["nsic_registration_number"]),
                epfo_establishment_code=as_text(row["epfo_establishment_code"]),
                employee_count=as_int(row["employee_count"]), enterprise_category=as_text(row["enterprise_category"]),
                state=as_text(row["state"]),
            )
            for row in new
        )
        await session.flush()
        session.add_all(
            Bid(bid_id=_bid_id(row), tender_id=row["target_tender_id"], bidder_id=row["bidder_id"],
                submitted_at=datetime.fromisoformat(row["submitted_at"]))
            for row in new
        )
        await session.flush()
        mine = [s for s in submissions if s["bidder_id"] in new_ids]
        session.add_all(
            BidDocumentSubmission(
                submission_id=s["submission_id"], bid_id=s["bid_id"], bidder_id=s["bidder_id"], tender_id=s["tender_id"],
                document_type=s["document_type"], submitted=as_bool(s["submitted"]), file_ref=as_text(s["file_ref"]),
                note=as_text(s["note"]),
            )
            for s in mine
        )
        session.add_all(
            BidDeclaration(
                declaration_id=d["declaration_id"], bid_id=d["bid_id"], bidder_id=d["bidder_id"], tender_id=d["tender_id"],
                criterion_code=d["criterion_code"], declared_value=d["declared_value"],
                declared_at=as_utc_datetime(d["declared_at"]), note=as_text(d["note"]),
            )
            for d in declarations
            if d["bidder_id"] in new_ids
        )
        # Placeholder document rows, exactly as app.db.seed creates them for the base fixture.
        session.add_all(
            Document(bid_id=s["bid_id"], doc_type=s["document_type"], file_url=s["file_ref"])
            for s in mine
            if as_bool(s["submitted"]) and s["file_ref"]
        )
        for row in new:
            debarment = portal[row["bidder_id"]].get("debarment", {})
            if debarment.get("status") == "debarred":
                start, until = split_debarment_period(debarment.get("debarment_period", ""))
                session.add(DebarredEntity(
                    pan=row["pan"], gstin=as_text(row["gstin"]), name=row["name"],
                    order_reference=debarment.get("order_reference"), debarred_from=start, debarred_until=until,
                    list_source=debarment.get("list_source"),
                ))
        await session.commit()
    print(f"inserted {len(new)} demo bidders and bids")
    return [_bid_id(row) for row in new]


async def verify(bid_ids: list[str]) -> dict[str, dict]:
    results = {}
    for i, bid_id in enumerate(bid_ids, 1):
        result = await run_pipeline_standalone(bid_id)
        results[bid_id] = result
        print(f"  [{i}/{len(bid_ids)}] {bid_id}: {result['overall_score']:.2f} {result['risk_level']}")
    return results


def _decision_for(rng: random.Random, result: dict) -> tuple[str, str] | None:
    """A plausible officer action, or None to leave the bid awaiting review."""
    risk, failures = result["risk_level"], result["mandatory_failure_reasons"]
    if risk == "Non-Compliant" and rng.random() < 0.55:
        return "disqualify", failures[0] if failures else "Fails a mandatory eligibility criterion."
    if risk == "Low" and rng.random() < 0.45:
        return "qualify", "All mandatory criteria verified; documents consistent with portal records."
    if risk in ("Medium", "High") and rng.random() < 0.35:
        return "request_clarification", "Please explain the discrepancy flagged in cross-verification and upload supporting documents."
    return None


async def decide(results: dict[str, dict]) -> None:
    rng = random.Random(7)
    count = 0
    for bid_id, result in results.items():
        choice = _decision_for(rng, result)
        if choice is None:
            continue
        decision, reason = choice
        async with SessionLocal() as session:
            await record_decision(bid_id, DecisionIn(decision=decision, actor=rng.choice(OFFICERS), reason=reason), session)
        count += 1
    print(f"recorded {count} officer decisions")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="remove demo bidders first")
    args = parser.parse_args()

    bidders, submissions, declarations, portal = _load()
    if args.reset:
        await reset(bidders)
    new_bid_ids = await insert(bidders, submissions, declarations, portal)
    if new_bid_ids:
        print(f"verifying {len(new_bid_ids)} bids through the pipeline ...")
        await decide(await verify(new_bid_ids))


if __name__ == "__main__":
    asyncio.run(main())
