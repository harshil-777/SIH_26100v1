"""Stage 7: advisory recommendation text, labeled AI-generated/advisory-only.

Deterministic template for now (no LLM key configured for this project) -- structured input
only, per BUILD_SPEC.md section 7's instruction to never send raw documents. Swapping this
for a real LLM call is a one-file change: keep the signature, replace the body with an API
call that receives the same `score` and `breakdown` structured facts.

Never persisted (compliance_scores has no column for it): computed fresh from persisted
data every time it's requested, so there is nothing to keep in sync with a real LLM later.
"""
from decimal import Decimal

ADVISORY_PREFIX = "AI-generated, advisory only: "

_CRITERION_LABELS = {
    "local_content_pct": "Make in India local content",
    "epfo_compliance": "EPFO/ESIC compliance",
    "declaration_document_consistency": "consistency between declarations, documents and portals",
    "msme_eligibility": "MSME eligibility",
}


def generate_recommendation(overall_score: Decimal | float, risk_level: str, breakdown: dict) -> str:
    reasons = breakdown.get("mandatory_failure_reasons") or []
    criteria = breakdown.get("criteria") or []

    if reasons:
        joined = " ".join(r if r.endswith(".") else f"{r}." for r in reasons)
        count = "a mandatory criterion" if len(reasons) == 1 else f"{len(reasons)} mandatory criteria"
        return (
            f"{ADVISORY_PREFIX}This bid failed {count}. {joined} "
            "Recommend disqualification, subject to officer review."
        )

    weak_graded = sorted(
        (c for c in criteria if c["type"] == "graded" and c["score"] is not None and c["score"] < 100),
        key=lambda c: c["score"],
    )
    if not weak_graded:
        return (
            f"{ADVISORY_PREFIX}Score {overall_score}/100 ({risk_level} risk). All mandatory "
            "and graded criteria passed cleanly. Recommend qualifying, subject to officer review."
        )

    weakest = weak_graded[0]
    weak_note = f" Weakest area: {_CRITERION_LABELS.get(weakest['id'], weakest['id'].replace('_', ' '))}."
    if weakest.get("reason"):
        weak_note += f" {weakest['reason']}"
    return (
        f"{ADVISORY_PREFIX}Score {overall_score}/100 ({risk_level} risk).{weak_note} "
        "Recommend officer review before qualifying."
    )
