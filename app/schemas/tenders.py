from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TenderCreate(BaseModel):
    tender_id: str
    title: str
    department: str
    category: Literal["Goods", "Services"]
    estimated_value_inr: Decimal
    msme_reserved: bool = False
    mii_local_content_threshold_pct: Decimal | None = None
    requires_oem_authorization: bool = False
    epfo_applicable_employee_threshold: int | None = None
    submission_deadline: date
    eligibility_rules_json: dict | None = None


class TenderOut(BaseModel):
    tender_id: str
    title: str
    department: str
    category: str
    estimated_value_inr: Decimal
    msme_reserved: bool
    mii_local_content_threshold_pct: Decimal | None
    requires_oem_authorization: bool
    epfo_applicable_employee_threshold: int | None
    submission_deadline: date
    eligibility_rules_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentRequirementOut(BaseModel):
    requirement_id: str
    tender_id: str
    document_type: str
    buyer_label: str | None
    requirement_source: str
    mandatory: bool
    notes: str | None

    model_config = {"from_attributes": True}
