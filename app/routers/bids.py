import asyncio
import hashlib
import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.config import get_settings
from app.db.session import get_session
from app.models import (
    Bid,
    BidDeclaration,
    BidDocumentSubmission,
    Bidder,
    ComplianceScore,
    Document,
    DocumentType,
    Tender,
    VerificationResult,
)
from app.schemas.bids import (
    AuditLogEntryOut,
    AuditLogOut,
    BidDetailOut,
    BidderSummary,
    BidCreate,
    BidOut,
    ComplianceScoreOut,
    DeclarationIn,
    DeclarationOut,
    DecisionIn,
    DecisionOut,
    DocumentOut,
    DocumentUploadOut,
    StatusOut,
    TenderSummary,
    VerificationResultOut,
    VerifyJobOut,
)
from app.services.audit import get_audit_log, verify_chain, write_audit_log
from app.services.object_store import get_object_store
from app.services.ocr import FILE_EXTENSIONS, detect_file_kind
from app.services.recommendation import generate_recommendation
from app.tasks import enqueue, ocr_document_task, verify_bid_task

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


@router.get("/{bid_id}", response_model=BidDetailOut)
async def get_bid(bid_id: str, session: AsyncSession = Depends(get_session)) -> BidDetailOut:
    bid = await _get_bid_or_404(session, bid_id)
    bidder = await session.get(Bidder, bid.bidder_id)
    tender = await session.get(Tender, bid.tender_id)

    declarations = (
        await session.execute(
            select(BidDeclaration)
            .where(BidDeclaration.bid_id == bid_id)
            .order_by(BidDeclaration.criterion_code)
        )
    ).scalars().all()
    latest_results = (
        await session.execute(
            select(VerificationResult)
            .where(VerificationResult.bid_id == bid_id)
            .distinct(VerificationResult.source)
            .order_by(VerificationResult.source, VerificationResult.verified_at.desc())
        )
    ).scalars().all()

    return BidDetailOut(
        bid_id=bid.bid_id,
        status=bid.status,
        submitted_at=bid.submitted_at,
        bidder=BidderSummary.model_validate(bidder),
        tender=TenderSummary.model_validate(tender),
        declarations=[DeclarationOut.model_validate(row) for row in declarations],
        verification_results=[VerificationResultOut.model_validate(row) for row in latest_results],
    )


async def _upsert_submission(
    session: AsyncSession,
    bid: Bid,
    document_type: str,
    *,
    submitted: bool,
    file_ref: str | None,
    note: str | None,
) -> BidDocumentSubmission:
    row = (
        await session.execute(
            select(BidDocumentSubmission).where(
                BidDocumentSubmission.bid_id == bid.bid_id,
                BidDocumentSubmission.document_type == document_type,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = BidDocumentSubmission(
            submission_id=f"S-{uuid.uuid4().hex[:12]}",
            bid_id=bid.bid_id,
            bidder_id=bid.bidder_id,
            tender_id=bid.tender_id,
            document_type=document_type,
        )
        session.add(row)
    row.submitted = submitted
    row.file_ref = file_ref
    row.note = note
    return row


@router.post("/{bid_id}/documents", response_model=DocumentUploadOut, status_code=201)
async def upload_document(
    bid_id: str,
    document_type: str = Form(...),
    note: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadOut:
    """Upload a document for OCR, or omit `file` to record an explicit non-submission."""
    bid = await _get_bid_or_404(session, bid_id)
    if await session.get(DocumentType, document_type) is None:
        raise HTTPException(422, f"Unknown document_type {document_type!r}")

    key = file_hash = kind = size = None
    if file is not None:
        max_mb = get_settings().max_upload_mb
        data = await file.read(max_mb * 1024 * 1024 + 1)
        if not data:
            raise HTTPException(400, "Uploaded file is empty")
        if len(data) > max_mb * 1024 * 1024:
            raise HTTPException(413, f"File exceeds the {max_mb} MB upload limit")
        kind = detect_file_kind(data)
        if kind is None:
            raise HTTPException(415, "Only PDF, PNG, JPEG and TIFF files are accepted")

        size = len(data)
        file_hash = hashlib.sha256(data).hexdigest()
        # Content-addressed: no client-supplied name ever reaches the storage path.
        key = f"documents/{file_hash}{FILE_EXTENSIONS[kind]}"
        # Stored before the DB commit, so no row can ever point at a missing file.
        await asyncio.to_thread(get_object_store().put, key, data)

    submission = await _upsert_submission(
        session, bid, document_type, submitted=file is not None, file_ref=key, note=note
    )
    doc = None
    if file is not None:
        doc = Document(bid_id=bid.bid_id, doc_type=document_type, file_url=key, file_hash=file_hash)
        session.add(doc)
    await session.commit()

    if doc is None:
        ocr_status = "not_applicable"
    elif enqueue(ocr_document_task, args=[str(doc.doc_id)], task_id=f"ocr-{doc.doc_id}"):
        ocr_status = "queued"
    else:
        ocr_status = "pending_verification"

    return DocumentUploadOut(
        submission_id=submission.submission_id,
        bid_id=bid.bid_id,
        document_type=document_type,
        submitted=submission.submitted,
        file_ref=submission.file_ref,
        note=submission.note,
        doc_id=doc.doc_id if doc else None,
        file_hash=file_hash,
        file_kind=kind,
        size_bytes=size,
        ocr_status=ocr_status,
    )


@router.get("/{bid_id}/documents", response_model=list[DocumentOut])
async def list_documents(bid_id: str, session: AsyncSession = Depends(get_session)) -> list[DocumentOut]:
    await _get_bid_or_404(session, bid_id)

    submissions = (
        await session.execute(
            select(BidDocumentSubmission)
            .where(BidDocumentSubmission.bid_id == bid_id)
            .order_by(BidDocumentSubmission.document_type)
        )
    ).scalars().all()
    documents = (
        await session.execute(
            select(Document).where(Document.bid_id == bid_id).order_by(Document.uploaded_at.asc())
        )
    ).scalars().all()
    latest = {doc.doc_type: doc for doc in documents}
    store = get_object_store()

    result = []
    for sub in submissions:
        doc = latest.get(sub.document_type)
        result.append(
            DocumentOut(
                document_type=sub.document_type,
                submitted=sub.submitted,
                file_ref=sub.file_ref,
                note=sub.note,
                doc_id=doc.doc_id if doc else None,
                file_hash=doc.file_hash if doc else None,
                uploaded_at=doc.uploaded_at if doc else None,
                is_placeholder=doc is not None and not store.exists(doc.file_url),
                ocr=doc.ocr_extracted_json if doc else None,
            )
        )
    return result


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
    if not enqueue(verify_bid_task, args=[bid_id], task_id=bid_id):
        raise HTTPException(503, "Job queue unavailable (is Redis running?). Try again shortly.")
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

    previous_status = bid.status
    bid.status = _DECISION_TO_STATUS[payload.decision]
    audit_row = await write_audit_log(
        session,
        bid_id=bid_id,
        actor=payload.actor,
        action="officer_decision",
        # actor and the status transition sit inside the hashed payload, so rewriting who
        # decided (or what the bid was before) breaks the chain rather than going unnoticed.
        payload={
            "decision": payload.decision,
            "reason": payload.reason,
            "actor": payload.actor,
            "previous_status": previous_status,
            "new_status": bid.status,
        },
    )
    await session.commit()

    return DecisionOut(bid_id=bid_id, status=bid.status, audit_log_id=audit_row.log_id)
