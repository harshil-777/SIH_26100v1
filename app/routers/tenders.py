from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fixtures import build_eligibility_rules_typed
from app.db.session import get_session
from app.models import Bid, ComplianceScore, Tender, TenderDocumentRequirement
from app.schemas.tenders import DocumentRequirementOut, TenderCreate, TenderListItem, TenderOut

router = APIRouter(prefix="/tenders", tags=["tenders"])

_RISK_RANK = {"Low": 1, "Medium": 2, "High": 3, "Non-Compliant": 4}
_RANK_TO_RISK = {v: k for k, v in _RISK_RANK.items()}


@router.get("", response_model=list[TenderListItem])
async def list_tenders(session: AsyncSession = Depends(get_session)) -> list[TenderListItem]:
    """Landing-page list: one row per tender, with how many bidders are participating."""
    latest_score = (
        select(ComplianceScore)
        .distinct(ComplianceScore.bid_id)
        .order_by(ComplianceScore.bid_id, ComplianceScore.generated_at.desc())
        .subquery()
    )
    risk_rank = case(*[(latest_score.c.risk_level == risk, rank) for risk, rank in _RISK_RANK.items()], else_=None)

    stmt = (
        select(
            Tender.tender_id,
            Tender.title,
            Tender.department,
            Tender.category,
            Tender.estimated_value_inr,
            Tender.msme_reserved,
            Tender.submission_deadline,
            func.count(Bid.bid_id).label("participant_count"),
            func.count(Bid.bid_id).filter(Bid.status.in_(["submitted", "under_review"])).label(
                "awaiting_decision_count"
            ),
            func.max(risk_rank).label("worst_risk_rank"),
        )
        .outerjoin(Bid, Bid.tender_id == Tender.tender_id)
        .outerjoin(latest_score, latest_score.c.bid_id == Bid.bid_id)
        .group_by(Tender.tender_id)
        .order_by(Tender.tender_id)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [
        TenderListItem(**{**row, "worst_risk_level": _RANK_TO_RISK.get(row["worst_risk_rank"])})
        for row in rows
    ]


@router.post("", response_model=TenderOut, status_code=201)
async def create_tender(
    payload: TenderCreate, session: AsyncSession = Depends(get_session)
) -> Tender:
    existing = await session.get(Tender, payload.tender_id)
    if existing is not None:
        raise HTTPException(409, f"Tender {payload.tender_id!r} already exists")

    rules_json = payload.eligibility_rules_json
    if rules_json is None:
        rules_json = build_eligibility_rules_typed(
            msme_reserved=payload.msme_reserved,
            mii_local_content_threshold_pct=payload.mii_local_content_threshold_pct,
            epfo_applicable_employee_threshold=payload.epfo_applicable_employee_threshold,
        )

    tender = Tender(
        tender_id=payload.tender_id,
        title=payload.title,
        department=payload.department,
        category=payload.category,
        estimated_value_inr=payload.estimated_value_inr,
        msme_reserved=payload.msme_reserved,
        mii_local_content_threshold_pct=payload.mii_local_content_threshold_pct,
        requires_oem_authorization=payload.requires_oem_authorization,
        epfo_applicable_employee_threshold=payload.epfo_applicable_employee_threshold,
        submission_deadline=payload.submission_deadline,
        eligibility_rules_json=rules_json,
    )
    session.add(tender)
    await session.commit()
    await session.refresh(tender)
    return tender


@router.get("/{tender_id}", response_model=TenderOut)
async def get_tender(tender_id: str, session: AsyncSession = Depends(get_session)) -> Tender:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(404, f"Tender {tender_id!r} not found")
    return tender


@router.get(
    "/{tender_id}/document-requirements", response_model=list[DocumentRequirementOut]
)
async def list_document_requirements(
    tender_id: str, session: AsyncSession = Depends(get_session)
) -> list[TenderDocumentRequirement]:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(404, f"Tender {tender_id!r} not found")
    rows = (
        await session.execute(
            select(TenderDocumentRequirement).where(
                TenderDocumentRequirement.tender_id == tender_id
            )
        )
    ).scalars().all()
    return list(rows)
