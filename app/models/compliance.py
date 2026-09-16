import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VerificationResult(Base):
    __tablename__ = "verification_results"

    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    bid_id: Mapped[str] = mapped_column(Text, ForeignKey("bids.bid_id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response_json: Mapped[dict | None] = mapped_column(JSONB)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ComplianceScore(Base):
    __tablename__ = "compliance_scores"
    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('Low','Medium','High','Non-Compliant')",
            name="compliance_scores_risk_level_check",
        ),
    )

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    bid_id: Mapped[str] = mapped_column(Text, ForeignKey("bids.bid_id"), nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    criterion_breakdown_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DebarredEntity(Base):
    __tablename__ = "debarred_entities"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    pan: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[str | None] = mapped_column(Text)
    debarred_from: Mapped[date | None] = mapped_column(Date)
    debarred_until: Mapped[date | None] = mapped_column(Date)
    list_source: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bid_id: Mapped[str | None] = mapped_column(Text, ForeignKey("bids.bid_id"))
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        "timestamp", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    prev_hash: Mapped[str | None] = mapped_column(Text)
    curr_hash: Mapped[str] = mapped_column(Text, nullable=False)
