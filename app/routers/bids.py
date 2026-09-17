import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db.session import get_session
from app.models import Bid, BidDeclaration, BidDocumentSubmission, Bidder, ComplianceScore, Tender
from app.schemas.bids import (
    AuditLogEntryOut,
    AuditLogOut,
    BidCreate,
    BidOut,
    ComplianceScoreOut,
    DeclarationIn,
    DeclarationOut,
    DecisionIn,
    DecisionOut,
    DocumentSubmissionIn,
    DocumentSubmissionOut,
    StatusOut,
    VerifyJobOut,
)
from app.services.audit import get_audit_log, verify_chain, write_audit_log
from app.services.recommendation import generate_recommendation
from app.tasks import verify_bid_task

router = APIRouter(prefix="/bids", tags=["bids"])

_DECISION_TO_STATUS = {
    "qualify": "qualified",
    "disqualify": "disqualified",
    "request_clarification": "clarification_requested",
}


async def _get_bid_or_404(session: AsyncSession, bid_id: str) -> Bid:
    bid = await session.get(Bid, bid_id)
    if bid is None:
        raise HTTPException(404, f"Bid {bid_id!r} not found")
    return bid


@router.post("", response_model=BidOut, status_code=201)
async def create_bid(payload: BidCreate, session: AsyncSession = Depends(get_session)) -> Bid:
    if await session.get(Tender, payload.tender_id) is None:
        raise HTTPException(404, f"Tender {payload.tender_id!r} not found")
    if await session.get(Bidder, payload.bidder_id) is None:
        raise HTTPException(404, f"Bidder {payload.bidder_id!r} not found")

    bid_id = f"BID-{payload.bidder_id}-{payload.tender_id}"
    existing = await session.get(Bid, bid_id)
    if existing is not None:
        return existing

    bid = Bid(bid_id=bid_id, tender_id=payload.tender_id, bidder_id=payload.bidder_id)
    session.add(bid)
    await session.commit()
    await session.refresh(bid)
    return bid


@router.post("/{bid_id}/documents", response_model=DocumentSubmissionOut, status_code=201)
async def register_document_submission(
    bid_id: str, payload: DocumentSubmissionIn, session: AsyncSession = Depends(get_session)
) -> BidDocumentSubmission:
    bid = await _get_bid_or_404(session, bid_id)

    existing = (
        await session.execute(
            select(BidDocumentSubmission).where(
                BidDocumentSubmission.bid_id == bid_id,
                BidDocumentSubmission.document_type == payload.document_type,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.submitted = payload.submitted
        existing.file_ref = payload.file_ref
        existing.note = payload.note
        row = existing
    else:
        row = BidDocumentSubmission(
            submission_id=f"S-{uuid.uuid4().hex[:12]}",
            bid_id=bid.bid_id,
            bidder_id=bid.bidder_id,
            tender_id=bid.tender_id,
            document_type=payload.document_type,
            submitted=payload.submitted,
            file_ref=payload.file_ref,
            note=payload.note,
        )
        session.add(row)

    await session.commit()
    await session.refresh(row)
    return row


@router.post("/{bid_id}/declarations", response_model=DeclarationOut, status_code=201)
async def submit_declaration(
    bid_id: str, payload: DeclarationIn, session: AsyncSession = Depends(get_session)
) -> BidDeclaration:
    bid = await _get_bid_or_404(session, bid_id)

    existing = (
        await session.execute(
            select(BidDeclaration).where(
                BidDeclaration.bid_id == bid_id,
                BidDeclaration.criterion_code == payload.criterion_code,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.declared_value = payload.declared_value
        existing.note = payload.note
        row = existing
    else:
        row = BidDeclaration(
            declaration_id=f"DC-{uuid.uuid4().hex[:12]}",
            bid_id=bid.bid_id,
            bidder_id=bid.bidder_id,
            tender_id=bid.tender_id,
            criterion_code=payload.criterion_code,
            declared_value=payload.declared_value,
            note=payload.note,
        )
        session.add(row)

    await session.commit()
    await session.refresh(row)
    return row


@router.post("/{bid_id}/verify", response_model=VerifyJobOut)
async def verify_bid(bid_id: str, session: AsyncSession = Depends(get_session)) -> VerifyJobOut:
    await _get_bid_or_404(session, bid_id)
    # task_id == bid_id: lets GET /status look up state without a separate jobs table.
    # Re-verifying a bid whose previous run already finished simply replaces that result.
    verify_bid_task.apply_async(args=[bid_id], task_id=bid_id)
    return VerifyJobOut(bid_id=bid_id, job_id=bid_id, status="queued")


@router.get("/{bid_id}/status", response_model=StatusOut)
async def get_bid_status(bid_id: str, session: AsyncSession = Depends(get_session)) -> StatusOut:
    await _get_bid_or_404(session, bid_id)

    result = AsyncResult(bid_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        job_status = "queued"
    elif state == "STARTED":
        job_status = "running"
    elif state == "SUCCESS":
        job_status = "success"
    elif state == "FAILURE":
        job_status = "failed"
    else:
        job_status = "queued"

    return StatusOut(
        bid_id=bid_id,
        job_status=job_status,
        celery_state=state,
        result=result.result if state == "SUCCESS" else None,
        error=str(result.result) if state == "FAILURE" else None,
    )


@router.get("/{bid_id}/compliance-score", response_model=ComplianceScoreOut)
async def get_compliance_score(
    bid_id: str, session: AsyncSession = Depends(get_session)
) -> ComplianceScoreOut:
    await _get_bid_or_404(session, bid_id)

    score = (
        await session.execute(
            select(ComplianceScore)
            .where(ComplianceScore.bid_id == bid_id)
            .order_by(ComplianceScore.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if score is None:
        raise HTTPException(404, f"No compliance score yet for bid {bid_id!r}")

    recommendation = generate_recommendation(
        score.overall_score, score.risk_level, score.criterion_breakdown_json
    )
    return ComplianceScoreOut(
        bid_id=bid_id,
        overall_score=score.overall_score,
        risk_level=score.risk_level,
        criterion_breakdown_json=score.criterion_breakdown_json,
        generated_at=score.generated_at,
        recommendation=recommendation,
    )


@router.get("/{bid_id}/audit-log", response_model=AuditLogOut)
async def get_bid_audit_log(bid_id: str, session: AsyncSession = Depends(get_session)) -> AuditLogOut:
    await _get_bid_or_404(session, bid_id)
    rows = await get_audit_log(session, bid_id)
    chain_valid, broken_at = verify_chain(rows)
    return AuditLogOut(
        bid_id=bid_id,
        chain_valid=chain_valid,
        broken_at=broken_at,
        entries=[AuditLogEntryOut.model_validate(row) for row in rows],
    )


@router.post("/{bid_id}/decision", response_model=DecisionOut)
async def record_decision(
    bid_id: str, payload: DecisionIn, session: AsyncSession = Depends(get_session)
) -> DecisionOut:
    bid = await _get_bid_or_404(session, bid_id)

    bid.status = _DECISION_TO_STATUS[payload.decision]
    audit_row = await write_audit_log(
        session,
        bid_id=bid_id,
        actor=payload.actor,
        action="officer_decision",
        payload={"decision": payload.decision, "reason": payload.reason},
    )
    await session.commit()

    return DecisionOut(bid_id=bid_id, status=bid.status, audit_log_id=audit_row.log_id)
