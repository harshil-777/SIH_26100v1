"""One-off backfill: store each already-verified bid's recommendation text in its
compliance_scores row, for bids verified before the pipeline started persisting it there.

    python scripts/backfill_recommendations.py

Without this, GET /bids/{id}/compliance-score recomputed the recommendation from scratch on
every single page view -- with ML_MODELS_ENABLED, that meant re-running the trained model's
generate() call (1-9s) on every visit to a bid's page, not just at verify-time. Safe to run
repeatedly and against a database with real traffic: read-only except for the one JSON field
it fills in, and it skips any row that already has one.
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import SessionLocal
from app.models import ComplianceScore
from app.services.recommendation import recommend


async def main() -> None:
    async with SessionLocal() as session:
        rows = (await session.execute(select(ComplianceScore))).scalars().all()
        updated = 0
        for score in rows:
            breakdown = score.criterion_breakdown_json
            if breakdown.get("recommendation"):
                continue
            result = recommend(score.overall_score, score.risk_level, breakdown)
            breakdown["recommendation"] = {"text": result["text"], "source": result["source"]}
            flag_modified(score, "criterion_breakdown_json")
            updated += 1
        await session.commit()
    print(f"backfilled {updated} of {len(rows)} compliance scores")


if __name__ == "__main__":
    asyncio.run(main())
