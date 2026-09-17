"""Stage 3: call every adapter in parallel and persist to verification_results.

VerificationAdapter.verify() is sync per BUILD_SPEC.md section 5's Protocol (a real live
adapter might use a sync HTTP client). To still satisfy section 7's "asyncio.gather, not
sequential awaits", each call is wrapped in asyncio.to_thread so they run concurrently
regardless of mode.
"""
import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import all_source_names, get_adapter
from app.models import VerificationResult

# mii_local_content reports percentages, not a status verb; still a "reported" fact.
_NO_STATUS_BUT_USABLE = "reported"


def _call_adapter(source: str, bidder_id: str) -> tuple[str, dict]:
    return source, dict(get_adapter(source).verify(bidder_id))


async def run_verification_stage(
    session: AsyncSession, bid_id: str, bidder_id: str
) -> dict[str, dict]:
    """Returns {source: raw_payload} for every source that isn't not_applicable/not_checked."""
    results = await asyncio.gather(
        *(asyncio.to_thread(_call_adapter, source, bidder_id) for source in all_source_names())
    )

    facts: dict[str, dict] = {}
    for source, result in results:
        status = result.get("status")
        raw = result.get("raw", result)

        if status == "not_applicable":
            continue
        if status is None:
            status = _NO_STATUS_BUT_USABLE if "verified_pct_estimate" in raw else "unknown"
        if status == "not_checked":
            # Absent from the fixture entirely -- nothing to persist or reason about.
            continue

        confidence = result.get("confidence")
        session.add(
            VerificationResult(
                bid_id=bid_id,
                source=source,
                status=status,
                raw_response_json=raw,
                confidence_score=Decimal(str(confidence)) if confidence is not None else None,
            )
        )
        facts[source] = raw

    await session.flush()
    return facts
