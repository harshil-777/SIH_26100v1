import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentType(Base):
    __tablename__ = "document_types"

    type_code: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to_category: Mapped[str | None] = mapped_column(Text)


class TenderDocumentRequirement(Base):
    __tablename__ = "tender_document_requirements"
    __table_args__ = (
        CheckConstraint(
            "requirement_source IN ('system_template',"
            "'buyer_selected_turnover_experience','buyer_atc','corrigendum')",
            name="tender_document_requirements_requirement_source_check",
        ),
    )

    requirement_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tenders.tender_id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        Text, ForeignKey("document_types.type_code"), nullable=False
    )
    buyer_label: Mapped[str | None] = mapped_column(Text)
    requirement_source: Mapped[str] = mapped_column(Text, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)


class BidDocumentSubmission(Base):
    __tablename__ = "bid_document_submissions"

    submission_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bid_id: Mapped[str] = mapped_column(Text, ForeignKey("bids.bid_id"), nullable=False)
    bidder_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bidders.bidder_id"), nullable=False
    )
    tender_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tenders.tender_id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        Text, ForeignKey("document_types.type_code"), nullable=False
    )
    submitted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    file_ref: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class BidDeclaration(Base):
    __tablename__ = "bid_declarations"

    declaration_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bid_id: Mapped[str] = mapped_column(Text, ForeignKey("bids.bid_id"), nullable=False)
    bidder_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bidders.bidder_id"), nullable=False
    )
    tender_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tenders.tender_id"), nullable=False
    )
    criterion_code: Mapped[str] = mapped_column(Text, nullable=False)
    declared_value: Mapped[str] = mapped_column(Text, nullable=False)
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    bid_id: Mapped[str] = mapped_column(Text, ForeignKey("bids.bid_id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        Text, ForeignKey("document_types.type_code"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_extracted_json: Mapped[dict | None] = mapped_column(JSONB)
    file_hash: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
