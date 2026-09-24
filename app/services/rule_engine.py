"""Stages 4 (cross-verification) and 5 (rule engine) of the orchestrator pipeline.

Per-criterion evaluation is dispatched by a hardcoded table keyed on criterion "id" rather
than a generic expression parser for the "source" strings in BUILD_SPEC.md section 8 --
there are only 8 known criterion IDs across every tender (see app/db/fixtures.py), so a
small closed dispatch table is the simplest thing that satisfies the DoD, per the spec's
own directive to prefer the simplest thing where it's silent on mechanism.
"""
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.mock_registry import get_registry
from app.models import Bidder, BidDeclaration
from app.services.completeness import CompletenessResult

_LOCAL_CONTENT_TOLERANCE_PCT = 2.0

_UDYAM_DOCS = ("UDYAM_CERTIFICATE", "EMD_EXEMPTION_PROOF")

# The fixture's document_cross_check doc_type -> the document_types it is a placeholder for.
# A real upload of any of these supersedes the placeholder entry.
_FIXTURE_PLACEHOLDER_FOR = {
    "gst_certificate": ("GST_CERTIFICATE",),
    "udyam_certificate": _UDYAM_DOCS,
    "local_content_self_certificate": ("MII_LOCAL_CONTENT_SELF_CERTIFICATE",),
    "epfo_compliance_certificate": ("EPFO_ESIC_COMPLIANCE_CERTIFICATE",),
    "pan_card": ("PAN_CARD",),
    "oem_authorization_letter": ("OEM_AUTHORIZATION_LETTER",),
    "dpiit_recognition_certificate": ("STARTUP_EMD_EXEMPTION_PROOF",),
}

_MSME_CATEGORIES = {"Micro", "Small", "Medium"}

# Wording for reasons shown to the officer; the comparison keys themselves stay machine-stable.
_FACT_LABELS = {
    "enterprise_category": "enterprise category",
    "local_content_pct": "local content %",
    "startup_recognized": "startup recognition",
    "manufacturer_or_trader": "manufacturer vs. trader",
    "gstin": "GSTIN",
    "gst_trade_name": "GST trade name",
    "gst_legal_name": "GST legal name",
    "pan": "PAN",
    "udyam_number": "Udyam number",
    "epfo_establishment_code": "EPFO establishment code",
    "dpiit_number": "DPIIT number",
}

# Documents that only a bidder claiming an MSE/startup exemption or preference can produce.
_EXEMPTION_PROOF_DOCS = {"EMD_EXEMPTION_PROOF"}

_LEGAL_SUFFIXES = {"private", "pvt", "limited", "ltd", "llp", "m/s", "ms", "the"}


@dataclass(frozen=True)
class Facts:
    bid_id: str
    tender_id: str
    bidder_id: str
    bidder_employee_count: int | None
    completeness: CompletenessResult
    portal_facts: dict[str, dict]  # source -> raw fixture payload
    ocr_facts: dict[str, dict]  # doc_type -> documents.ocr_extracted_json ({} for placeholders)
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


def _document_label(doc_type: str) -> str:
    return doc_type.replace("_", " ").lower()


def _fact_label(key: str) -> str:
    if key.startswith("placeholder:"):
        return f"{_document_label(key.removeprefix('placeholder:'))} (seeded document check)"
    return _FACT_LABELS.get(key, key.replace("_", " "))


def _can_claim_mse_or_startup_exemption(facts: Facts) -> bool:
    udyam = facts.portal_facts.get("udyam") or {}
    startup = facts.portal_facts.get("startup_india") or {}
    is_mse = _recognized_status(udyam.get("status")) and udyam.get("category") in _MSME_CATEGORIES
    return is_mse or _recognized_status(startup.get("status"))


def _eval_document_completeness(criterion: dict, facts: Facts) -> CriterionOutcome:
    # An exemption/preference proof can only come from a bidder the portals show is eligible to
    # claim one. When they show it isn't, the missing proof is a symptom of ineligibility --
    # judged on its own by msme_eligibility for reserved tenders -- not a paperwork gap, and
    # reporting it as one would give the officer the wrong reason (seed bid B010).
    claimable = _can_claim_mse_or_startup_exemption(facts)
    gaps, not_applicable = [], []
    for m in facts.completeness.missing:
        entry = {"document_type": m.document_type, "buyer_label": m.buyer_label}
        (not_applicable if m.document_type in _EXEMPTION_PROOF_DOCS and not claimable else gaps).append(entry)

    passed = not gaps
    reason = None
    if not passed:
        labels = ", ".join(g["buyer_label"] or g["document_type"] for g in gaps)
        reason = f"Missing mandatory document(s): {labels}"
    evidence: dict[str, Any] = {"missing_documents": gaps}
    if not_applicable:
        evidence["not_applicable_documents"] = [
            {**entry, "why": "Bidder is not a portal-verified MSE or recognized startup, so this exemption proof cannot apply."}
            for entry in not_applicable
        ]
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=passed,
        score=None,
        weight=None,
        evidence=evidence,
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
            "document_pct": _as_float(
                _extracted_fields(facts, "MII_LOCAL_CONTENT_SELF_CERTIFICATE").get("local_content_pct")
            ),
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


def _extracted_fields(facts: Facts, doc_type: str) -> dict:
    result = facts.ocr_facts.get(doc_type) or {}
    if result.get("status") != "extracted":
        return {}
    return result.get("fields") or {}


def _portal(source: str, key: str) -> Callable[[Facts], Any]:
    return lambda f: (f.portal_facts.get(source) or {}).get(key)


def _declared(criterion_code: str) -> Callable[[Facts], Any]:
    return lambda f: f.declarations.get(criterion_code)


def _casefold(value: Any) -> str | None:
    text = str(value).strip().casefold()
    return text or None


def _compact_upper(value: Any) -> str | None:
    text = re.sub(r"\s", "", str(value)).upper()
    return text or None


def _name_tokens(value: Any) -> frozenset[str] | None:
    """'Om Security & Facility Services Pvt. Ltd.' -> {om, security, and, facility, services}."""
    text = str(value).casefold().replace("&", " and ")
    tokens = frozenset(re.findall(r"[a-z0-9]+", text)) - _LEGAL_SUFFIXES
    return tokens or None


def _activity_roles(value: Any) -> frozenset[str] | None:
    text = str(value).casefold()
    if not text.strip():
        return None
    roles = {role for role, stem in (("manufacturer", "manufactur"), ("trader", "trad")) if stem in text}
    return frozenset(roles or {"other"})


def _declared_role(value: Any) -> frozenset[str] | None:
    text = str(value).strip().casefold()
    if text == "manufacturer":
        return frozenset({"manufacturer"})
    if text in ("trader", "trading"):
        return frozenset({"trader"})
    return None


def _recognized_status(value: Any) -> bool:
    return str(value).strip().casefold() in ("valid", "active", "recognized")


def _still_valid(value: Any) -> bool | None:
    try:
        return date.fromisoformat(str(value)) >= date.today()
    except ValueError:
        return None


@dataclass(frozen=True)
class _FactSpec:
    """One fact that may be stated by the declaration, a document, and/or the portal."""

    key: str
    equal: Callable[[Any, Any], bool]
    canon: Callable[[Any], Any]
    declared: Callable[[Facts], Any] | None = None
    canon_declared: Callable[[Any], Any] | None = None
    document_types: tuple[str, ...] = ()
    document_field: str | None = None
    canon_document: Callable[[Any], Any] | None = None
    portal: Callable[[Facts], Any] | None = None


_same = lambda a, b: a == b  # noqa: E731

_FACT_SPECS = (
    _FactSpec(
        key="enterprise_category",
        declared=_declared("enterprise_category_self_declared"),
        document_types=_UDYAM_DOCS,
        document_field="enterprise_category",
        portal=_portal("udyam", "category"),
        canon=_casefold,
        equal=_same,
    ),
    _FactSpec(
        key="local_content_pct",
        declared=_declared("local_content_pct_self_declared"),
        document_types=("MII_LOCAL_CONTENT_SELF_CERTIFICATE",),
        document_field="local_content_pct",
        portal=_portal("mii_local_content", "verified_pct_estimate"),
        canon=_as_float,
        equal=lambda a, b: abs(a - b) <= _LOCAL_CONTENT_TOLERANCE_PCT,
    ),
    _FactSpec(
        key="startup_recognized",
        declared=_declared("startup_status_self_declared"),
        canon_declared=lambda v: "recognized" in str(v).casefold(),
        document_types=("STARTUP_EMD_EXEMPTION_PROOF",),
        document_field="valid_until",
        canon_document=_still_valid,
        portal=_portal("startup_india", "status"),
        canon=_recognized_status,
        equal=_same,
    ),
    _FactSpec(
        key="manufacturer_or_trader",
        declared=_declared("manufacturer_or_trader_self_declared"),
        canon_declared=_declared_role,
        document_types=_UDYAM_DOCS,
        document_field="activity",
        portal=_portal("udyam", "activity"),
        canon=_activity_roles,
        equal=lambda a, b: bool(a & b),
    ),
    _FactSpec(
        key="gstin",
        document_types=("GST_CERTIFICATE",),
        document_field="gstin",
        portal=_portal("gstn", "gstin"),
        canon=_compact_upper,
        equal=_same,
    ),
    _FactSpec(
        key="gst_trade_name",
        document_types=("GST_CERTIFICATE",),
        document_field="trade_name",
        portal=_portal("gstn", "trade_name"),
        canon=_name_tokens,
        equal=_same,
    ),
    _FactSpec(
        key="gst_legal_name",
        document_types=("GST_CERTIFICATE",),
        document_field="legal_name",
        portal=_portal("gstn", "legal_name"),
        canon=_name_tokens,
        equal=_same,
    ),
    _FactSpec(
        key="pan",
        document_types=("PAN_CARD",),
        document_field="pan",
        portal=_portal("pan", "pan"),
        canon=_compact_upper,
        equal=_same,
    ),
    _FactSpec(
        key="udyam_number",
        document_types=_UDYAM_DOCS,
        document_field="udyam_number",
        portal=_portal("udyam", "registration_number"),
        canon=_compact_upper,
        equal=_same,
    ),
    _FactSpec(
        key="epfo_establishment_code",
        document_types=("EPFO_ESIC_COMPLIANCE_CERTIFICATE",),
        document_field="establishment_code",
        portal=_portal("epfo_esic", "establishment_code"),
        canon=_compact_upper,
        equal=_same,
    ),
    _FactSpec(
        key="dpiit_number",
        document_types=("STARTUP_EMD_EXEMPTION_PROOF",),
        document_field="dpiit_number",
        portal=_portal("startup_india", "recognition_number"),
        canon=_compact_upper,
        equal=_same,
    ),
)


def _compare_fact(spec: _FactSpec, facts: Facts) -> dict | None:
    """Compares every available pair among declared/document/portal; None if < 2 sources."""
    sources: dict[str, tuple[Any, Any]] = {}  # name -> (raw value for display, canonical)
    evidence: dict[str, Any] = {}

    if spec.declared and (raw := spec.declared(facts)) is not None:
        canon = (spec.canon_declared or spec.canon)(raw)
        if canon is not None:
            sources["declared"] = (raw, canon)

    for doc_type in spec.document_types:
        raw = _extracted_fields(facts, doc_type).get(spec.document_field)
        if raw is None:
            continue
        canon = (spec.canon_document or spec.canon)(raw)
        if canon is not None:
            sources["document"] = (raw, canon)
            evidence["document_type"] = doc_type
            break

    if spec.portal and (raw := spec.portal(facts)) is not None:
        canon = spec.canon(raw)
        if canon is not None:
            sources["portal"] = (raw, canon)

    if len(sources) < 2:
        return None

    names = list(sources)
    mismatched_pairs = [
        f"{a}_vs_{b}"
        for i, a in enumerate(names)
        for b in names[i + 1 :]
        if not spec.equal(sources[a][1], sources[b][1])
    ]
    return {
        **{name: raw for name, (raw, _) in sources.items()},
        **evidence,
        "match": not mismatched_pairs,
        "mismatched_pairs": mismatched_pairs,
    }


def _eval_declaration_document_consistency(criterion: dict, facts: Facts) -> CriterionOutcome:
    """Stage 4's three-way check: declaration vs. document vs. portal, per fact.

    A document's real OCR fields feed the "document" leg. The fixture's pre-computed
    document_cross_check is used only as a placeholder for document types that have no
    real upload yet, and is superseded as soon as one exists.
    """
    comparisons: dict[str, dict] = {}
    for spec in _FACT_SPECS:
        if (comparison := _compare_fact(spec, facts)) is not None:
            comparisons[spec.key] = comparison

    real_uploads = {doc_type for doc_type, result in facts.ocr_facts.items() if result.get("status")}
    superseded = []
    for entry in facts.document_cross_check:
        placeholder_type = entry.get("doc_type", "document")
        if real_uploads.intersection(_FIXTURE_PLACEHOLDER_FOR.get(placeholder_type, ())):
            superseded.append(placeholder_type)
            continue
        if entry.get("match") is not None:
            comparisons[f"placeholder:{placeholder_type}"] = {
                "match": entry["match"],
                "note": entry.get("note"),
            }

    unreadable = {
        doc_type: result.get("error") or result["status"]
        for doc_type, result in facts.ocr_facts.items()
        if result.get("status") and result["status"] != "extracted"
    }

    compared = len(comparisons)
    matches = sum(1 for c in comparisons.values() if c["match"])
    score = 100.0 if compared == 0 else 100.0 * matches / compared

    reasons = []
    if mismatched := [_fact_label(key) for key, c in comparisons.items() if not c["match"]]:
        reasons.append(
            f"Declaration/document does not match portal-verified data for: {', '.join(mismatched)}."
        )
    if unreadable:
        reasons.append(f"Could not read uploaded document(s): {', '.join(map(_document_label, unreadable))}.")

    return CriterionOutcome(
        id=criterion["id"],
        type="graded",
        passed=None,
        score=score,
        weight=criterion["weight"],
        evidence={
            "comparisons": comparisons,
            "superseded_placeholders": superseded,
            "unreadable_documents": unreadable,
        },
        reason=" ".join(reasons) or None,
    )


def _eval_msme_eligibility(criterion: dict, facts: Facts) -> CriterionOutcome:
    udyam = facts.portal_facts.get("udyam") or {}
    category = udyam.get("category") if _recognized_status(udyam.get("status")) else None
    eligible = category in _MSME_CATEGORIES
    reason = None
    if not eligible:
        reason = (
            f"Ineligible for this MSME-reserved tender: portal-verified enterprise category is "
            f"'{category or 'not registered on Udyam'}'. This is a tender eligibility bar, not a "
            "statutory compliance failure."
        )
    evidence = {"portal_category": category, "udyam_status": udyam.get("status")}

    # Tenders seeded before reservation became a hard bar carry it as a graded criterion;
    # score those the old way so an existing tender's config keeps meaning what it said.
    if criterion.get("type") == "graded":
        return CriterionOutcome(
            id=criterion["id"],
            type="graded",
            passed=None,
            score=100.0 if eligible else 0.0,
            weight=criterion["weight"],
            evidence=evidence,
            reason=reason,
        )
    return CriterionOutcome(
        id=criterion["id"],
        type="mandatory",
        passed=eligible,
        score=None,
        weight=None,
        evidence=evidence,
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
