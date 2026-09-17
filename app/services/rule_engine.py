"""Stages 4 (cross-verification) and 5 (rule engine) of the orchestrator pipeline.

Per-criterion evaluation is dispatched by a hardcoded table keyed on criterion "id" rather
than a generic expression parser for the "source" strings in BUILD_SPEC.md section 8 --
there are only 8 known criterion IDs across every tender (see app/db/fixtures.py), so a
small closed dispatch table is the simplest thing that satisfies the DoD, per the spec's
own directive to prefer the simplest thing where it's silent on mechanism.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.mock_registry import get_registry
from app.models import Bidder, BidDeclaration
from app.services.completeness import CompletenessResult

# Declaration criterion_code -> function pulling the comparable portal-verified value.
_DECLARATION_PORTAL_FIELD: dict[str, Callable[["Facts"], Any]] = {
    "enterprise_category_self_declared": lambda f: (f.portal_facts.get("udyam") or {}).get(
        "category"
    ),
    "local_content_pct_self_declared": lambda f: (
        f.portal_facts.get("mii_local_content") or {}
    ).get("verified_pct_estimate"),
    "startup_status_self_declared": lambda f: (
        f.portal_facts.get("startup_india") or {}
    ).get("status"),
}

_LOCAL_CONTENT_TOLERANCE_PCT = 2.0


@dataclass(frozen=True)
class Facts:
    bid_id: str
    tender_id: str
    bidder_id: str
    bidder_employee_count: int | None
    completeness: CompletenessResult
    portal_facts: dict[str, dict]  # source -> raw fixture payload
    ocr_facts: dict[str, dict]  # doc_type -> extracted fields (empty in Phase 1)
    declarations: dict[str, str]  # criterion_code -> declared_value
    document_cross_check: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class CriterionOutcome:
    id: str
    type: str  # "mandatory" | "graded"
    passed: bool | None  # set for mandatory
    score: float | None  # 0-100, set for graded
    weight: float | None  # set for graded
    evidence: dict[str, Any]
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "passed": self.passed,
            "score": self.score,
            "weight": self.weight,
            "evidence": self.evidence,
            "reason": self.reason,
        }


async def gather_facts(
    session: AsyncSession,
    *,
    bid_id: str,
    tender_id: str,
    bidder_id: str,
    completeness: CompletenessResult,
    portal_facts: dict[str, dict],
    ocr_facts: dict[str, dict],
) -> Facts:
    bidder = (
        await session.execute(select(Bidder).where(Bidder.bidder_id == bidder_id))
    ).scalar_one()

    declaration_rows = (
        await session.execute(
            select(BidDeclaration)
            .where(BidDeclaration.bid_id == bid_id)
            .order_by(BidDeclaration.declared_at.asc())
        )
    ).scalars().all()
    # Later rows win if a criterion_code was ever re-declared.
    declarations = {row.criterion_code: row.declared_value for row in declaration_rows}

    return Facts(
        bid_id=bid_id,
        tender_id=tender_id,
        bidder_id=bidder_id,
        bidder_employee_count=bidder.employee_count,
        completeness=completeness,
        portal_facts=portal_facts,
        ocr_facts=ocr_facts,
        declarations=declarations,
        document_cross_check=get_registry().document_cross_check(bidder_id),
    )


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _eval_gst_active(criterion: dict, facts: Facts) -> CriterionOutcome:
    status = (facts.portal_facts.get("gstn") or {}).get("status")
    passed = status == "active"
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=passed,
        score=None,
        weight=None,
        evidence={"portal_status": status},
        reason=None if passed else f"GSTN status is '{status or 'unavailable'}', expected 'active'.",
    )


def _eval_not_debarred(criterion: dict, facts: Facts) -> CriterionOutcome:
    status = (facts.portal_facts.get("debarment") or {}).get("status")
    passed = status == "clear"
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=passed,
        score=None,
        weight=None,
        evidence={"portal_status": status},
        reason=None if passed else f"Debarment registry status is '{status or 'unavailable'}', expected 'clear'.",
    )


def _eval_pan_valid(criterion: dict, facts: Facts) -> CriterionOutcome:
    status = (facts.portal_facts.get("pan") or {}).get("status")
    passed = status == "valid"
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=passed,
        score=None,
        weight=None,
        evidence={"portal_status": status},
        reason=None if passed else f"PAN verification status is '{status or 'unavailable'}', expected 'valid'.",
    )


def _eval_document_completeness(criterion: dict, facts: Facts) -> CriterionOutcome:
    passed = facts.completeness.passed
    missing = [
        {"document_type": m.document_type, "buyer_label": m.buyer_label}
        for m in facts.completeness.missing
    ]
    reason = None
    if not passed:
        labels = ", ".join(m.buyer_label or m.document_type for m in facts.completeness.missing)
        reason = f"Missing mandatory document(s): {labels}"
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=passed,
        score=None,
        weight=None,
        evidence={"missing_documents": missing},
        reason=reason,
    )


def _eval_local_content_pct(criterion: dict, facts: Facts) -> CriterionOutcome:
    threshold = criterion["threshold"]
    verified_pct = _as_float((facts.portal_facts.get("mii_local_content") or {}).get("verified_pct_estimate"))
    declared_pct = _as_float(facts.declarations.get("local_content_pct_self_declared"))

    if verified_pct is None:
        score = 0.0
        reason = "No MII local-content verification available from the portal."
    elif verified_pct >= threshold:
        score = 100.0
        reason = None
    else:
        score = max(0.0, 100.0 * verified_pct / threshold)
        reason = f"Verified local content ({verified_pct}%) is below the {threshold}% threshold."

    return CriterionOutcome(
        id=criterion["id"],
        type="graded",
        passed=None,
        score=score,
        weight=criterion["weight"],
        evidence={
            "portal_verified_pct": verified_pct,
            "declared_pct": declared_pct,
            "threshold": threshold,
        },
        reason=reason,
    )


def _eval_epfo_compliance(criterion: dict, facts: Facts) -> CriterionOutcome:
    registered = (facts.portal_facts.get("epfo_esic") or {}).get("registered_employee_count")
    declared = facts.bidder_employee_count

    if registered is None or declared is None:
        score = 0.0
        reason = "EPFO-registered employee count unavailable for comparison."
    elif registered == declared:
        score = 100.0
        reason = None
    else:
        score = 0.0
        reason = f"Declared employee count ({declared}) does not match EPFO-registered count ({registered})."

    return CriterionOutcome(
        id=criterion["id"],
        type="graded",
        passed=None,
        score=score,
        weight=criterion["weight"],
        evidence={"declared_employee_count": declared, "epfo_registered_employee_count": registered},
        reason=reason,
    )


def _declaration_matches_portal(criterion_code: str, declared_value: str, portal_value: Any) -> bool | None:
    if criterion_code == "enterprise_category_self_declared":
        if portal_value is None:
            return None
        return declared_value.strip().lower() == str(portal_value).strip().lower()

    if criterion_code == "local_content_pct_self_declared":
        declared = _as_float(declared_value)
        portal = _as_float(portal_value)
        if declared is None or portal is None:
            return None
        return abs(declared - portal) <= _LOCAL_CONTENT_TOLERANCE_PCT

    if criterion_code == "startup_status_self_declared":
        if portal_value is None:
            return None
        declared_recognized = "recognized" in declared_value.strip().lower()
        portal_recognized = str(portal_value).strip().lower() in ("valid", "active", "recognized")
        return declared_recognized == portal_recognized

    return None


def _eval_declaration_document_consistency(criterion: dict, facts: Facts) -> CriterionOutcome:
    comparisons: dict[str, dict] = {}
    matches = 0
    compared = 0

    # The document leg of the three-way check: Phase 1 has no real OCR (see
    # app/services/ocr.py), so document_cross_check -- the fixture's pre-computed
    # document-vs-portal comparison -- stands in for what OCR would otherwise feed here.
    for entry in facts.document_cross_check:
        match = entry.get("match")
        doc_type = entry.get("doc_type", "document")
        comparisons[f"document:{doc_type}"] = {
            "declared": None,
            "portal": None,
            "document_match": match,
            "note": entry.get("note"),
        }
        if match is not None:
            compared += 1
            matches += int(match)

    for criterion_code, declared_value in facts.declarations.items():
        if criterion_code == "manufacturer_or_trader_self_declared":
            activity = str((facts.portal_facts.get("udyam") or {}).get("activity") or "").lower()
            if not activity:
                match = None
            elif declared_value.strip().lower() == "manufacturer":
                match = "manufactur" in activity
            elif declared_value.strip().lower() in ("trader", "trading"):
                match = "trad" in activity
            else:
                match = None
            comparisons[criterion_code] = {
                "declared": declared_value,
                "portal": (facts.portal_facts.get("udyam") or {}).get("activity"),
                "match": match,
            }
        elif criterion_code in _DECLARATION_PORTAL_FIELD:
            portal_value = _DECLARATION_PORTAL_FIELD[criterion_code](facts)
            match = _declaration_matches_portal(criterion_code, declared_value, portal_value)
            comparisons[criterion_code] = {
                "declared": declared_value,
                "portal": portal_value,
                "match": match,
            }
        else:
            continue

        if match is not None:
            compared += 1
            matches += int(match)

    score = 100.0 if compared == 0 else 100.0 * matches / compared
    mismatched = [
        code
        for code, c in comparisons.items()
        if c.get("match") is False or c.get("document_match") is False
    ]
    reason = None
    if mismatched:
        reason = f"Declaration/document does not match portal-verified data for: {', '.join(mismatched)}."

    return CriterionOutcome(
        id=criterion["id"],
        type="graded",
        passed=None,
        score=score,
        weight=criterion["weight"],
        evidence={"comparisons": comparisons},
        reason=reason,
    )


def _eval_msme_eligibility(criterion: dict, facts: Facts) -> CriterionOutcome:
    category = (facts.portal_facts.get("udyam") or {}).get("category")
    eligible_categories = {"Micro", "Small", "Medium"}
    passed_categories = category in eligible_categories
    score = 100.0 if passed_categories else 0.0
    reason = None
    if not passed_categories:
        reason = (
            f"Portal-verified enterprise category is "
            f"'{category or 'not registered on Udyam'}', not eligible for this "
            "MSME-reserved tender."
        )

    return CriterionOutcome(
        id=criterion["id"],
        type="graded",
        passed=None,
        score=score,
        weight=criterion["weight"],
        evidence={"portal_category": category},
        reason=reason,
    )


_EVALUATORS: dict[str, Callable[[dict, Facts], CriterionOutcome]] = {
    "gst_active": _eval_gst_active,
    "not_debarred": _eval_not_debarred,
    "pan_valid": _eval_pan_valid,
    "document_completeness": _eval_document_completeness,
    "local_content_pct": _eval_local_content_pct,
    "epfo_compliance": _eval_epfo_compliance,
    "declaration_document_consistency": _eval_declaration_document_consistency,
    "msme_eligibility": _eval_msme_eligibility,
}


def evaluate_criteria(eligibility_rules_json: dict, facts: Facts) -> list[CriterionOutcome]:
    outcomes = []
    for criterion in eligibility_rules_json.get("criteria", []):
        criterion_id = criterion["id"]
        try:
            evaluator = _EVALUATORS[criterion_id]
        except KeyError:
            raise ValueError(f"No rule-engine evaluator registered for criterion {criterion_id!r}") from None
        outcomes.append(evaluator(criterion, facts))
    return outcomes
