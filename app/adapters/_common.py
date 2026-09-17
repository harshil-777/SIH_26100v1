"""Shared base so each of the 9 adapter files stays a 3-line declaration.

Not itself a VerificationAdapter listed in BUILD_SPEC.md section 2 -- it's the mode-switch
plumbing (mock vs. live) that every concrete adapter reuses.
"""
from app.adapters.base import VerificationResult
from app.adapters.mock_registry import get_registry
from app.config import get_settings


class MockOrLiveAdapter:
    source_name: str

    def verify(self, bidder_id: str) -> VerificationResult:
        mode = get_settings().adapter_mode
        if mode == "mock":
            return get_registry().verify(self.source_name, bidder_id)
        if mode == "live":
            raise NotImplementedError(
                f"ADAPTER_MODE=live has no real client for {self.source_name!r} yet "
                "(see BUILD_SPEC.md section 10: non-goals)."
            )
        raise ValueError(f"Unknown ADAPTER_MODE: {mode!r}")
