"""Score breakdown -> findings -> the recommendation model's input text.

A breakdown is compliance_scores.criterion_breakdown_json, exactly as the orchestrator stores
it. The model only ever sees this structured summary -- never a raw document (BUILD_SPEC.md
section 7, stage 7).
"""

# Words a recommendation must use when it reports a finding of this type -- and must not use
# when no such finding exists (evaluation counts that as an invented finding).
#
# Each phrase is unique to its type: no other finding's templates use it, so its presence is
# unambiguous evidence the finding was reported (checked by ml/recommendation/targets.py's tests).
KEYWORDS = {
    "gst_inactive": "gst registration",
    "debarred": "debar",
    "pan_invalid": "pan verification",
    "missing_documents": "missing",
    "msme_ineligible": "reserved",
    "local_content_shortfall": "below the required",
    "local_content_unverified": "could not be verified",
    "epfo_mismatch": "epfo records",
    "epfo_unverified": "epfo data",
    "unreadable": "legible",
    "mismatch:enterprise_category": "enterprise category",
    "mismatch:local_content_pct": "local content figures",
    "mismatch:startup_recognized": "startup",
    "mismatch:manufacturer_or_trader": "manufactur",
    "mismatch:gstin": "gstin",
    "mismatch:gst_trade_name": "trade name",
    "mismatch:gst_legal_name": "legal name",
    "mismatch:pan": "pan card",
    "mismatch:udyam_number": "udyam registration number",
    "mismatch:epfo_establishment_code": "establishment code",
    "mismatch:dpiit_number": "dpiit",
}
MANDATORY_TYPES = {"gst_inactive", "debarred", "pan_invalid", "missing_documents", "msme_ineligible"}


def finding_key(finding: dict) -> str:
    if finding["type"] == "mismatch":
        fact = finding["fact"].removeprefix("placeholder:")
        fact = {"gst_certificate": "gst_trade_name", "udyam_certificate": "enterprise_category",
                "local_content_self_certificate": "local_content_pct", "epfo_compliance_certificate": "epfo_establishment_code",
                "pan_card": "pan", "dpiit_recognition_certificate": "startup_recognized",
                "oem_authorization_letter": "gstin"}.get(fact, fact)
        return f"mismatch:{fact}"
    return finding["type"]


def findings_from_breakdown(breakdown: dict) -> list[dict]:
    findings = []
    for c in breakdown.get("criteria", []):
        ev = c.get("evidence") or {}
        if c["type"] == "mandatory" and c["passed"] is False:
            if c["id"] == "gst_active":
                findings.append({"type": "gst_inactive", "status": ev.get("portal_status") or "unavailable"})
            elif c["id"] == "not_debarred":
                findings.append({"type": "debarred", "status": ev.get("portal_status") or "unavailable"})
            elif c["id"] == "pan_valid":
                findings.append({"type": "pan_invalid", "status": ev.get("portal_status") or "unavailable"})
            elif c["id"] == "document_completeness":
                docs = [m.get("buyer_label") or m["document_type"] for m in ev.get("missing_documents", [])]
                findings.append({"type": "missing_documents", "documents": docs})
            elif c["id"] == "msme_eligibility":
                findings.append({"type": "msme_ineligible", "category": ev.get("portal_category") or "not registered on Udyam"})
        elif c["type"] == "graded" and c["id"] == "local_content_pct" and (c.get("score") or 0) < 100:
            if ev.get("portal_verified_pct") is None:
                findings.append({"type": "local_content_unverified", "threshold": ev.get("threshold")})
            else:
                findings.append({"type": "local_content_shortfall", "verified": ev["portal_verified_pct"], "threshold": ev.get("threshold")})
        elif c["type"] == "graded" and c["id"] == "epfo_compliance" and (c.get("score") or 0) < 100:
            if ev.get("epfo_registered_employee_count") is None:
                findings.append({"type": "epfo_unverified"})
            else:
                findings.append({"type": "epfo_mismatch", "declared": ev.get("declared_employee_count"),
                                 "registered": ev["epfo_registered_employee_count"]})
        elif c["id"] == "declaration_document_consistency":
            for key, comparison in (ev.get("comparisons") or {}).items():
                if comparison.get("match") is False:
                    findings.append({"type": "mismatch", "fact": key, "declared": comparison.get("declared"),
                                     "document": comparison.get("document"), "portal": comparison.get("portal")})
            for doc_type in ev.get("unreadable_documents") or {}:
                findings.append({"type": "unreadable", "document": doc_type})
    return findings


def verdict(risk_level: str, findings: list[dict]) -> str:
    if any(f["type"] in MANDATORY_TYPES for f in findings):
        return "disqualify"
    if risk_level == "Low" and not findings:
        return "qualify"
    return "review"


def _compact(finding: dict) -> str:
    parts = [finding_key(finding)]
    for key in ("status", "documents", "category", "verified", "threshold", "declared", "registered", "document", "portal"):
        value = finding.get(key)
        if value not in (None, [], ""):
            parts.append(f"{key}={', '.join(map(str, value)) if isinstance(value, list) else value}")
    return " ".join(parts)


def build_input(overall_score, risk_level: str, breakdown: dict) -> str:
    """The exact text the model is conditioned on, at training and inference time alike."""
    findings = findings_from_breakdown(breakdown)
    rendered = " ; ".join(_compact(f) for f in findings) or "none"
    return f"write recommendation | risk: {risk_level} | score: {float(overall_score):.1f} | findings: {rendered}"
