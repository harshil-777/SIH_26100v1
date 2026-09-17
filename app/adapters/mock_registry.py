"""Loads dummy_mock_portal_responses.json once and serves it to every mock adapter.

Business logic (rule engine, scoring, dashboard) never imports this module directly —
only the per-source adapter classes do, and only when ADAPTER_MODE=mock.
"""
import json
from functools import lru_cache
from typing import Any

from app.adapters.base import VerificationResult
from app.config import get_settings

_NOT_CHECKED: VerificationResult = {"status": "not_checked"}


class MockPortalRegistry:
    def __init__(self, bidders_by_id: dict[str, dict[str, Any]]):
        self._bidders = bidders_by_id

    def verify(self, source: str, bidder_id: str) -> VerificationResult:
        bidder = self._bidders.get(bidder_id)
        if bidder is None:
            return dict(_NOT_CHECKED)
        payload = bidder.get(source)
        if not isinstance(payload, dict):
            return dict(_NOT_CHECKED)

        result: VerificationResult = {"raw": payload}
        if "status" in payload:
            result["status"] = payload["status"]
        if "confidence" in payload:
            result["confidence"] = payload["confidence"]
        if "verified_at" in payload:
            result["verified_at"] = payload["verified_at"]
        return result

    def document_cross_check(self, bidder_id: str) -> list[dict[str, Any]]:
        """The fixture's stand-in for OCR-derived document/portal comparisons.

        Real OCR doesn't exist until Phase 2, so this pre-computed array is how the
        fixture simulates what stage 4 (cross-verification) would otherwise derive from
        documents.ocr_extracted_json.
        """
        bidder = self._bidders.get(bidder_id)
        if bidder is None:
            return []
        cross_check = bidder.get("document_cross_check")
        return cross_check if isinstance(cross_check, list) else []


@lru_cache
def get_registry() -> MockPortalRegistry:
    data_dir = get_settings().seed_data_dir
    payload = json.loads((data_dir / "dummy_mock_portal_responses.json").read_text(encoding="utf-8"))
    bidders_by_id = {entry["bidder_id"]: entry for entry in payload["bidders"]}
    return MockPortalRegistry(bidders_by_id)
