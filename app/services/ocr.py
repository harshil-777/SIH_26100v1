"""Stage 2: document extraction.

Text comes from the PDF's own text layer when it has one (most GST/Udyam/MII certificates
are generated digitally, so no OCR is needed), and from Tesseract for images and scanned
PDFs. Regexes then pull structured fields out of that text, and the result is stored in
documents.ocr_extracted_json for stage 4's cross-verification.

Seeded placeholder documents have no file in the object store, so for them this stage is
still a no-op, exactly as in Phase 1.
"""
import asyncio
import io
import re
import uuid
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import pdfplumber
import pytesseract
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import BidDocumentSubmission, Document
from app.services.object_store import get_object_store

FILE_EXTENSIONS = {"pdf": ".pdf", "png": ".png", "jpeg": ".jpg", "tiff": ".tiff"}

# Below this many non-whitespace characters, a PDF is treated as scanned and OCR'd.
_MIN_TEXT_LAYER_CHARS = 20
_RASTER_DPI = 300
_EXCERPT_CHARS = 1500
_WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_UDYAM_RE = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b")
_CIN_RE = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
_EPFO_CODE_RE = re.compile(r"\b[A-Z]{2}/[A-Z]{3}/\d{7}/\d{3}\b")
_DPIIT_RE = re.compile(r"\bDIPP\d{3,8}\b")

_LABELLED = {
    "trade_name": re.compile(r"^[ \t]*Trade\s+Name(?:\s*,?\s*if\s+any)?[ \t]*[:\-]?[ \t]*(.+?)[ \t]*$", re.I | re.M),
    "legal_name": re.compile(
        r"^[ \t]*Legal\s+Name(?:\s+of\s+(?:the\s+)?Business)?[ \t]*[:\-]?[ \t]*(.+?)[ \t]*$", re.I | re.M
    ),
    "activity": re.compile(
        r"^[ \t]*(?:Major\s+|Nature\s+of\s+|Type\s+of\s+)?Activity[ \t]*[:\-]?[ \t]*(.+?)[ \t]*$", re.I | re.M
    ),
}
_CATEGORY_RE = re.compile(
    r"\b(?:category|type\s+of\s+enterprise|enterprise\s+type|classification)\b[^\n:]*[:\-]?\s*"
    r"(micro|small|medium|large)\b",
    re.I,
)
_LOCAL_CONTENT_RE = re.compile(r"local\s+content[^%]{0,80}?(\d{1,3}(?:\.\d{1,2})?)\s*%", re.I)
# MII certificates usually restate the tender's threshold ("meets the minimum local content
# of 50%") before giving the actual figure; those mentions must not be read as the figure.
_THRESHOLD_WORDS_RE = re.compile(r"minimum|required|requirement|threshold|at\s+least", re.I)
# Only explicit end-of-validity labels: a GST certificate's "Date of Validity: <start> to ..."
# is a start date and must not be read as an expiry.
_VALID_UNTIL_RE = re.compile(
    r"\b(?:valid(?:ity)?\s+(?:until|upto|up\s+to|till|through)|expiry\s+date|expires\s+on)\b[^\n\d]{0,15}",
    re.I,
)

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
)}
_DATE_PATTERNS = (
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})[ -]([A-Za-z]{3,9})[ ,-]+(\d{4})\b"), "d_mon_y"),
    (re.compile(r"\b([A-Za-z]{3,9}) (\d{1,2}),? (\d{4})\b"), "mon_d_y"),
)


class OcrUnavailable(Exception):
    pass


def detect_file_kind(data: bytes) -> str | None:
    """Identify the file from its leading bytes, never from the client's content-type."""
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    return None


@lru_cache
def _configure_tesseract() -> None:
    cmd = get_settings().tesseract_cmd
    if cmd is None and _WINDOWS_TESSERACT.is_file():
        cmd = str(_WINDOWS_TESSERACT)
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def _ocr_image(image: Image.Image) -> str:
    _configure_tesseract()
    try:
        return pytesseract.image_to_string(image.convert("L"))
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailable("Tesseract is not installed or not on PATH (set TESSERACT_CMD)") from exc


def _meaningful_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def extract_text(data: bytes, kind: str) -> tuple[str, str, int, int]:
    """Returns (text, method, page_count, pages_processed)."""
    max_pages = get_settings().ocr_max_pages

    if kind != "pdf":
        with Image.open(io.BytesIO(data)) as image:
            return _ocr_image(image), "tesseract", 1, 1

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = pdf.pages[:max_pages]
        text = "\n".join(page.extract_text() or "" for page in pages)
        if _meaningful_chars(text) >= _MIN_TEXT_LAYER_CHARS:
            return text, "pdf_text_layer", len(pdf.pages), len(pages)

        scanned = "\n".join(
            _ocr_image(page.to_image(resolution=_RASTER_DPI).original) for page in pages
        )
        return scanned, "pdf_tesseract", len(pdf.pages), len(pages)


def _parse_date(text: str) -> date | None:
    for pattern, order in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        a, b, c = match.groups()
        try:
            if order == "ymd":
                return date(int(a), int(b), int(c))
            if order == "dmy":
                return date(int(c), int(b), int(a))
            if order == "d_mon_y":
                month = _MONTHS.get(b[:3].lower())
                return date(int(c), month, int(a)) if month else None
            month = _MONTHS.get(a[:3].lower())
            return date(int(c), month, int(b)) if month else None
        except ValueError:
            continue
    return None


def _local_content_pct(text: str) -> float | None:
    for match in _LOCAL_CONTENT_RE.finditer(text):
        # Look back only to the start of this sentence, not into the previous one.
        sentence_start = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
        context = text[max(sentence_start, match.start() - 40) : match.end()]
        if not _THRESHOLD_WORDS_RE.search(context):
            return float(match.group(1))
    return None


def parse_fields(text: str) -> dict:
    """Pull the structured fields stage 4 compares. Missing fields are simply omitted."""
    upper = text.upper()
    fields: dict = {}

    for name, pattern in (
        ("gstin", _GSTIN_RE),
        ("pan", _PAN_RE),
        ("udyam_number", _UDYAM_RE),
        ("cin", _CIN_RE),
        ("establishment_code", _EPFO_CODE_RE),
        ("dpiit_number", _DPIIT_RE),
    ):
        if match := pattern.search(upper):
            fields[name] = match.group(0)

    for name, pattern in _LABELLED.items():
        if match := pattern.search(text):
            fields[name] = match.group(1).strip()

    if match := _CATEGORY_RE.search(text):
        fields["enterprise_category"] = match.group(1).title()

    if (local_content := _local_content_pct(text)) is not None:
        fields["local_content_pct"] = local_content

    if match := _VALID_UNTIL_RE.search(text):
        if valid_until := _parse_date(text[match.end() : match.end() + 40]):
            fields["valid_until"] = valid_until.isoformat()

    return fields


def extract_document(data: bytes, file_hash: str) -> dict:
    """Builds the documents.ocr_extracted_json payload. Never raises."""
    result: dict = {
        "file_hash": file_hash,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "method": None,
        "fields": {},
    }
    kind = detect_file_kind(data)
    if kind is None:
        return {**result, "status": "failed", "error": "Unsupported file type"}

    try:
        text, method, page_count, pages_processed = extract_text(data, kind)
    except OcrUnavailable as exc:
        return {**result, "status": "ocr_unavailable", "error": str(exc)}
    except Exception as exc:  # corrupt/encrypted PDFs, undecodable images, ...
        return {**result, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    result.update(
        method=method,
        page_count=page_count,
        pages_processed=pages_processed,
        char_count=_meaningful_chars(text),
        text_excerpt=text[:_EXCERPT_CHARS],
    )
    if _meaningful_chars(text) == 0:
        return {**result, "status": "no_text"}
    return {**result, "status": "extracted", "fields": parse_fields(text)}


def _needs_extraction(doc: Document) -> bool:
    existing = doc.ocr_extracted_json
    if not existing or existing.get("file_hash") != doc.file_hash:
        return True
    # Tesseract may have been installed since; everything else is deterministic.
    return existing.get("status") == "ocr_unavailable"


async def _ensure_extracted(doc: Document) -> dict:
    store = get_object_store()
    if not store.exists(doc.file_url):
        # Seeded placeholder with no real file behind it.
        return doc.ocr_extracted_json or {}
    if not _needs_extraction(doc):
        return doc.ocr_extracted_json

    data = await asyncio.to_thread(store.get, doc.file_url)
    result = await asyncio.to_thread(extract_document, data, doc.file_hash)
    doc.ocr_extracted_json = result
    return result


async def run_ocr_stage(session: AsyncSession, bid_id: str) -> dict[str, dict]:
    """Extraction results for this bid, keyed by doc_type.

    Only the latest upload per doc_type counts, and only for doc_types the bid currently
    marks as submitted -- a later explicit non-submission overrides an earlier upload.
    """
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
    documents = (
        await session.execute(
            select(Document).where(Document.bid_id == bid_id).order_by(Document.uploaded_at.asc())
        )
    ).scalars().all()
    latest = {doc.doc_type: doc for doc in documents}

    results = {}
    for doc_type, doc in latest.items():
        if doc_type in submitted_types:
            results[doc_type] = await _ensure_extracted(doc)
    await session.flush()
    return results


async def run_ocr_for_document(doc_id: str) -> dict:
    """Entry point for the upload-time Celery task."""
    async with SessionLocal() as session:
        doc = await session.get(Document, uuid.UUID(doc_id))
        if doc is None:
            return {"doc_id": doc_id, "status": "missing"}
        result = await _ensure_extracted(doc)
        await session.commit()
        return {"doc_id": doc_id, "status": result.get("status")}
