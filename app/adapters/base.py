from typing import Any, Protocol, TypedDict


class VerificationResult(TypedDict, total=False):
    status: str
    confidence: float
    verified_at: str
    raw: dict[str, Any]


class VerificationAdapter(Protocol):
    source_name: str

    def verify(self, bidder_id: str) -> VerificationResult: ...
