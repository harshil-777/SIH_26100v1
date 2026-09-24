"""Run every seed bid end to end and check it against dummy_bidders.csv's expected_ground_truth.

Run from the repo root with the API and worker up:
    python scripts/check_ground_truth.py              # re-verify all 12 bids, then check
    python scripts/check_ground_truth.py --no-run     # check the latest stored scores only
    python scripts/check_ground_truth.py --api http://localhost:8000

Exits non-zero if any bid misses its expectation. Each run of the first form appends one normal
verify_completed entry to every bid's audit log, exactly as clicking "Re-run verification" would.

expected_ground_truth is free text, so each scenario_tag's meaning is pinned down below as the
checks it implies: the risk band, which mandatory criterion (if any) must be the one that fails,
and which flag must be raised. Uses only the standard library so it runs from any Python 3.11+.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

SEED_BIDDERS = Path(__file__).resolve().parent.parent / "WORKING DOCUMENTS" / "dummy_bidders.csv"
NOT_NON_COMPLIANT = {"Low", "Medium", "High"}

Breakdown = dict
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


def _request(api: str, method: str, path: str) -> dict:
    req = urllib.request.Request(f"{api}{path}", method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def _seed_bids() -> list[dict]:
    with SEED_BIDDERS.open(newline="") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        return [
            {**row, "bid_id": f"BID-{row['bidder_id']}-{row['target_tender_id']}"}
            for row in rows
            if row.get("scenario_tag")
        ]


def _verify_all(api: str, bid_ids: list[str], timeout_s: float = 300) -> dict[str, str]:
    """Queue every bid, then wait for all of them. Returns bid_id -> error for any that failed."""
    for bid_id in bid_ids:
        _request(api, "POST", f"/bids/{bid_id}/verify")
    pending, errors = set(bid_ids), {}
    deadline = time.monotonic() + timeout_s
    while pending and time.monotonic() < deadline:
        time.sleep(2)
        for bid_id in sorted(pending):
            try:
                status = _request(api, "GET", f"/bids/{bid_id}/status")
            except (urllib.error.URLError, TimeoutError):
                continue  # transient; the job itself keeps running
            if status["job_status"] == "success":
                pending.discard(bid_id)
            elif status["job_status"] == "failed":
                pending.discard(bid_id)
                errors[bid_id] = status.get("error") or "failed"
    errors.update({bid_id: "timed out" for bid_id in pending})
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--no-run", action="store_true", help="check the latest stored scores without re-verifying")
    args = parser.parse_args()

    bids = _seed_bids()
    unknown = sorted({b["scenario_tag"] for b in bids} - EXPECTATIONS.keys())
    if unknown:
        print(f"No expectation defined for scenario(s): {unknown}")
        return 2

    run_errors = {} if args.no_run else _verify_all(args.api, [b["bid_id"] for b in bids])

    failures = 0
    for bid in bids:
        bid_id, tag = bid["bid_id"], bid["scenario_tag"]
        allowed, checks, should_qualify = EXPECTATIONS[tag]
        if bid_id in run_errors:
            problems = [f"pipeline {run_errors[bid_id]}"]
            score = None
        else:
            score = _request(args.api, "GET", f"/bids/{bid_id}/compliance-score")
            breakdown = score["criterion_breakdown_json"]
            problems = [] if score["risk_level"] in allowed else [f"risk {score['risk_level']}, expected {'/'.join(sorted(allowed))}"]
            problems += [p for p in (check(breakdown) for check in checks) if p]
            if should_qualify and "Recommend qualifying" not in score["recommendation"]:
                problems.append("recommendation does not advise qualifying")

        failures += bool(problems)
        result = f"{score['overall_score']:>6} {score['risk_level']:<13}" if score else " " * 20
        print(f"{'PASS' if not problems else 'FAIL'}  {bid_id}  {result} {tag}")
        for problem in problems:
            print(f"        - {problem}")
        if problems:
            print(f"        expected: {bid['expected_ground_truth']}")

    print(f"\n{len(bids) - failures}/{len(bids)} seed bids match their expected ground truth.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
