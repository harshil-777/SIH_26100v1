"""Stage 2: document extraction.

Phase 1 has no real uploaded files -- every documents row is a synthetic placeholder from
the seeder with ocr_extracted_json left NULL. This stage is therefore a genuine no-op: it
reads whatever's already there (nothing, in Phase 1) and never fabricates content. Phase 2
replaces extract() with real OCR against uploaded PDFs/images.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


def extract(document: Document) -> dict:
    """Return the document's existing extracted fields, or {} if none exist yet."""
    return document.ocr_extracted_json or {}


async def run_ocr_stage(session: AsyncSession, bid_id: str) -> dict[str, dict]:
    """OCR facts for this bid, keyed by doc_type. No-op in Phase 1 (see module docstring)."""
    documents = (
        await session.execute(select(Document).where(Document.bid_id == bid_id))
    ).scalars().all()
    return {doc.doc_type: extract(doc) for doc in documents}
