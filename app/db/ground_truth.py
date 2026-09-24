"""What each seed scenario's expected_ground_truth (dummy_bidders.csv) means, as checks.

expected_ground_truth is free text, so each scenario_tag is pinned down here as the checks it
implies: the risk band, which mandatory criterion (if any) must be the one that fails -- so a bid
can't pass for the wrong reason -- and which flag must be raised. Shared by
scripts/check_ground_truth.py (against a running API) and tests/integration (against a throwaway
database). Imports nothing from the app, so the script can run on a bare Python.
"""
from collections.abc import Callable

NOT_NON_COMPLIANT = {"Low", "Medium", "High"}

Breakdown = dict  # a compliance_scores.criterion_breakdown_json
Check = Callable[[Breakdown], str | None]  # returns a failure message, or None when satisfied


def _criteria(b: Breakdown) -> dict[str, dict]:
    return {c["id"]: c for c in b["criteria"]}


def fails_only(*criterion_ids: str) -> Check:
    """Exactly these mandatory criteria fail -- the bid is out for the scenario's reason, not another."""

    def check(b: Breakdown) -> str | None:
        failing = sorted(c["id"] for c in b["criteria"] if c["type"] == "mandatory" and c["passed"] is False)
        return None if failing == sorted(criterion_ids) else f"mandatory failures {failing}, expected {sorted(criterion_ids)}"

    return check


def graded_below_100(criterion_id: str) -> Check:
    def check(b: Breakdown) -> str | None:
        c = _criteria(b).get(criterion_id)
        if c is None:
            return f"criterion {criterion_id} not evaluated"
        return None if c["score"] is not None and c["score"] < 100 else f"{criterion_id} scored {c['score']}, expected a shortfall"

    return check


def mismatch_on(*fact_keys: str) -> Check:
    """At least one of these facts is flagged as a mismatch in the cross-verification."""

    def check(b: Breakdown) -> str | None:
        consistency = _criteria(b).get("declaration_document_consistency") or {}
        comparisons = (consistency.get("evidence") or {}).get("comparisons") or {}
        for key in fact_keys:
            comparison = comparisons.get(key)
            if comparison and (comparison.get("match") is False or comparison.get("document_match") is False):
                return None
        return f"no mismatch flagged on any of {list(fact_keys)}"

    return check


def missing_document(document_type: str) -> Check:
    def check(b: Breakdown) -> str | None:
        completeness = _criteria(b).get("document_completeness") or {}
        missing = [m["document_type"] for m in (completeness.get("evidence") or {}).get("missing_documents", [])]
        return None if document_type in missing else f"{document_type} not reported missing (missing: {missing})"

    return check


# scenario_tag -> (allowed risk levels, extra checks, recommendation must say to qualify)
EXPECTATIONS: dict[str, tuple[set[str], list[Check], bool]] = {
    "clean_compliant": ({"Low"}, [fails_only()], True),
    "gst_cancelled": ({"Non-Compliant"}, [fails_only("gst_active")], False),
    "pan_invalid": ({"Non-Compliant"}, [fails_only("pan_valid")], False),
    # Declared Small vs portal Medium: flagged, but Medium is still an MSME, so still eligible.
    "udyam_category_mismatch": (NOT_NON_COMPLIANT, [fails_only(), mismatch_on("enterprise_category", "placeholder:udyam_certificate")], False),
    "blacklisted": ({"Non-Compliant"}, [fails_only("not_debarred")], False),
    "local_content_below_threshold": (NOT_NON_COMPLIANT, [fails_only(), graded_below_100("local_content_pct")], False),
    "epfo_mismatch": (NOT_NON_COMPLIANT, [fails_only(), graded_below_100("epfo_compliance")], False),
    "startup_recognition_expired": (NOT_NON_COMPLIANT, [fails_only(), mismatch_on("startup_recognized", "placeholder:dpiit_recognition_certificate")], False),
    "document_portal_name_mismatch": (NOT_NON_COMPLIANT, [fails_only(), mismatch_on("gst_trade_name", "placeholder:gst_certificate")], False),
    # Statutory checks pass; out only on the tender's MSME reservation -- not a document gap.
    "not_msme_ineligible_for_reservation": ({"Non-Compliant"}, [fails_only("msme_eligibility")], False),
    "clean_compliant_non_msme": ({"Low"}, [fails_only()], True),
    "missing_oem_authorization": ({"Non-Compliant"}, [fails_only("document_completeness"), missing_document("OEM_AUTHORIZATION_LETTER")], False),
}




def evaluate(scenario_tag: str, risk_level: str, breakdown: Breakdown, recommendation: str) -> list[str]:
    """Every way this scored bid misses its scenario's expectation; empty when it matches."""
    allowed, checks, should_qualify = EXPECTATIONS[scenario_tag]
    problems = [] if risk_level in allowed else [f"risk {risk_level}, expected {'/'.join(sorted(allowed))}"]
    problems += [p for p in (check(breakdown) for check in checks) if p]
    if should_qualify and "Recommend qualifying" not in recommendation:
        problems.append("recommendation does not advise qualifying")
    return problems
