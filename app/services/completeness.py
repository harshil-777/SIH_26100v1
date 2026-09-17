"""Stage 1: diff mandatory tender_document_requirements against bid_document_submissions."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BidDocumentSubmission, TenderDocumentRequirement


@dataclass(frozen=True)
class MissingRequirement:
    document_type: str
    requirement_id: str
    buyer_label: str | None


@dataclass(frozen=True)
class CompletenessResult:
    passed: bool
    missing: list[MissingRequirement]


async def check_completeness(
    session: AsyncSession, tender_id: str, bid_id: str
) -> CompletenessResult:
    mandatory_reqs = (
        await session.execute(
            select(TenderDocumentRequirement).where(
                TenderDocumentRequirement.tender_id == tender_id,
                TenderDocumentRequirement.mandatory.is_(True),
            )
        )
    ).scalars().all()

    submitted_types = set(
        (
            await session.execute(
                select(BidDocumentSubmission.document_type).where(
                    BidDocumentSubmission.bid_id == bid_id,
                    BidDocumentSubmission.submitted.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    missing = [
        MissingRequirement(
            document_type=req.document_type,
            requirement_id=req.requirement_id,
            buyer_label=req.buyer_label,
        )
        for req in mandatory_reqs
        if req.document_type not in submitted_types
    ]

    return CompletenessResult(passed=not missing, missing=missing)
