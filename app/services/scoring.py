"""Stage 6: compliance score + risk band (BUILD_SPEC.md section 8's scoring rule)."""
from decimal import Decimal

from app.models import ComplianceScore
from app.services.rule_engine import CriterionOutcome

MANDATORY_FAILURE_CAP = 40.0
LOW_RISK_THRESHOLD = 85.0
MEDIUM_RISK_THRESHOLD = 60.0


def compute_score(outcomes: list[CriterionOutcome]) -> tuple[float, str, dict]:
    graded = [o for o in outcomes if o.type == "graded"]
    mandatory_failures = [o for o in outcomes if o.type == "mandatory" and not o.passed]

    total_weight = sum(o.weight for o in graded)
    graded_score = (
        sum(o.weight * o.score for o in graded) / total_weight if total_weight > 0 else 100.0
    )

    if mandatory_failures:
        overall_score = min(graded_score, MANDATORY_FAILURE_CAP)
        risk_level = "Non-Compliant"
    else:
        overall_score = graded_score
        if overall_score >= LOW_RISK_THRESHOLD:
            risk_level = "Low"
        elif overall_score >= MEDIUM_RISK_THRESHOLD:
            risk_level = "Medium"
        else:
            risk_level = "High"

    mandatory_failure_reasons = [o.reason for o in mandatory_failures if o.reason]
    breakdown = {
        "criteria": [o.to_dict() for o in outcomes],
        "graded_weighted_score": round(graded_score, 2),
        "mandatory_failure_reasons": mandatory_failure_reasons,
    }
    return round(overall_score, 2), risk_level, breakdown


def build_compliance_score(bid_id: str, outcomes: list[CriterionOutcome]) -> ComplianceScore:
    overall_score, risk_level, breakdown = compute_score(outcomes)
    return ComplianceScore(
        bid_id=bid_id,
        # asyncpg binds NUMERIC strictly (same lesson as the earlier DATE-column bug):
        # Decimal(str(x)) avoids float binary-imprecision artifacts vs. Decimal(x) directly.
        overall_score=Decimal(str(overall_score)),
        risk_level=risk_level,
        criterion_breakdown_json=breakdown,
    )
