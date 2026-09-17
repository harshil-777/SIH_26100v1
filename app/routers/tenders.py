from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fixtures import build_eligibility_rules_typed
from app.db.session import get_session
from app.models import Tender, TenderDocumentRequirement
from app.schemas.tenders import DocumentRequirementOut, TenderCreate, TenderOut

router = APIRouter(prefix="/tenders", tags=["tenders"])


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
