"""Run every seed bid end to end and check it against dummy_bidders.csv's expected_ground_truth.

Run from the repo root with the API and worker up:
    python scripts/check_ground_truth.py              # re-verify all 12 bids, then check
    python scripts/check_ground_truth.py --no-run     # check the latest stored scores only
    python scripts/check_ground_truth.py --api http://localhost:8000

Exits non-zero if any bid misses its expectation. Each run of the first form appends one normal
verify_completed entry to every bid's audit log, exactly as clicking "Re-run verification" would.

What each scenario's free-text expectation means is pinned down in app/db/ground_truth.py,
shared with the integration tests. Needs only the standard library, so it runs from any
Python 3.11+ without the app's dependencies installed.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.db.ground_truth import EXPECTATIONS, evaluate  # noqa: E402

SEED_BIDDERS = REPO_ROOT / "WORKING DOCUMENTS" / "dummy_bidders.csv"


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
        if bid_id in run_errors:
            problems = [f"pipeline {run_errors[bid_id]}"]
            score = None
        else:
            score = _request(args.api, "GET", f"/bids/{bid_id}/compliance-score")
            problems = evaluate(tag, score["risk_level"], score["criterion_breakdown_json"], score["recommendation"])

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
