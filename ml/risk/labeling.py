"""Score a synthetic bid with the app's real rule engine, so labels match production logic.

Imports the app (needs sqlalchemy + pydantic-settings; no database). Only the data generators
use this -- training and inference never do.
"""
from decimal import Decimal

from app.db.fixtures import build_eligibility_rules_typed
from app.services.completeness import CompletenessResult, MissingRequirement
from app.services.rule_engine import Facts, evaluate_criteria
from app.services.scoring import compute_score


def rules_for(tender: dict) -> dict:
    threshold = tender.get("mii_threshold") or 0
    return build_eligibility_rules_typed(
        msme_reserved=bool(tender["msme_reserved"]),
        mii_local_content_threshold_pct=Decimal(str(threshold)) if threshold else None,
        epfo_applicable_employee_threshold=20 if tender["epfo_applicable"] else None,
    )


def to_facts(bid: dict) -> Facts:
    missing = [
        MissingRequirement(document_type=d, requirement_id=f"R-{d}", buyer_label=d.replace("_", " ").title())
        for d in bid["missing_docs"]
    ]
    return Facts(
        bid_id="SYNTHETIC",
        tender_id="SYNTHETIC",
        bidder_id="SYNTHETIC",
        bidder_employee_count=bid["employees"],
        completeness=CompletenessResult(passed=not missing, missing=missing),
        portal_facts=bid["portal"],
        ocr_facts=bid["ocr"],
        declarations=bid["declarations"],
        document_cross_check=[],
    )


def score_bid(tender: dict, bid: dict) -> tuple[float, str, dict]:
    """(overall_score, risk_level, breakdown) exactly as the orchestrator's stages 4-6 compute them."""
    return compute_score(evaluate_criteria(rules_for(tender), to_facts(bid)))
