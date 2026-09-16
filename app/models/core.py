import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','procurement_officer','auditor','bidder')",
            name="users_role_check",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        CheckConstraint("category IN ('Goods','Services')", name="tenders_category_check"),
    )

    tender_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_value_inr: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    msme_reserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    mii_local_content_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    requires_oem_authorization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    epfo_applicable_employee_threshold: Mapped[int | None] = mapped_column(Integer)
    submission_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    eligibility_rules_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Bidder(Base):
    __tablename__ = "bidders"
    __table_args__ = (
        CheckConstraint(
            "enterprise_category IN ('Micro','Small','Medium','Large')",
            name="bidders_enterprise_category_check",
        ),
    )

    bidder_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    pan: Mapped[str] = mapped_column(Text, nullable=False)
    gstin: Mapped[str | None] = mapped_column(Text)
    udyam_number: Mapped[str | None] = mapped_column(Text)
    cin: Mapped[str | None] = mapped_column(Text)
    dpiit_recognition_number: Mapped[str | None] = mapped_column(Text)
    nsic_registration_number: Mapped[str | None] = mapped_column(Text)
    epfo_establishment_code: Mapped[str | None] = mapped_column(Text)
    employee_count: Mapped[int | None] = mapped_column(Integer)
    enterprise_category: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','under_review','qualified','disqualified',"
            "'clarification_requested')",
            name="bids_status_check",
        ),
        UniqueConstraint("tender_id", "bidder_id", name="bids_tender_id_bidder_id_key"),
    )

    bid_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tenders.tender_id"), nullable=False
    )
    bidder_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bidders.bidder_id"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="submitted")
