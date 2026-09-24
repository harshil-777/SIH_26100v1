"""Small builders for rule-engine inputs, so each test states only what it is about."""
from app.services.completeness import CompletenessResult, MissingRequirement
from app.services.rule_engine import CriterionOutcome, Facts

CLEAN_PORTALS = {
    "gstn": {"status": "active", "gstin": "27AABCN1234A1Z5", "legal_name": "Nova Electro Systems Private Limited", "trade_name": "Nova Electro Systems"},
    "pan": {"status": "valid", "pan": "AABCN1234A"},
    "debarment": {"status": "clear"},
    "udyam": {"status": "valid", "category": "Small", "registration_number": "UDYAM-MH-03-0012345"},
    "startup_india": {"status": "not_applicable"},
    "epfo_esic": {"status": "active", "registered_employee_count": 45},
    "mii_local_content": {"verified_pct_estimate": 55},
}


def make_facts(*, portals=None, missing=(), declarations=None, ocr=None, employees=45, cross_check=None) -> Facts:
    merged = {**CLEAN_PORTALS, **(portals or {})}
    return Facts(
        bid_id="BID-T",
        tender_id="T-1",
        bidder_id="B-T",
        bidder_employee_count=employees,
        completeness=CompletenessResult(
            passed=not missing,
            missing=[MissingRequirement(document_type=d, requirement_id=f"R-{d}", buyer_label=f"Annexure {d}") for d in missing],
        ),
        portal_facts={k: v for k, v in merged.items() if v is not None},
        ocr_facts=ocr or {},
        declarations=declarations or {},
        document_cross_check=cross_check or [],
    )


def mandatory(id_: str, passed: bool, reason: str | None = None) -> CriterionOutcome:
    return CriterionOutcome(id=id_, type="mandatory", passed=passed, score=None, weight=None, evidence={}, reason=reason)


def graded(id_: str, score: float, weight: float, reason: str | None = None) -> CriterionOutcome:
    return CriterionOutcome(id=id_, type="graded", passed=None, score=score, weight=weight, evidence={}, reason=reason)
