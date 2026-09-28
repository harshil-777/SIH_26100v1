"""Bid facts -> the risk model's feature vector.

Input is what the pipeline observes, as plain dicts (no app imports), so the same code runs
in training, inside the app, and standalone from the Hugging Face repo:

    featurize(tender, observed)
      tender:   {"msme_reserved", "mii_threshold", "epfo_applicable", "mandatory_docs"}
      observed: {"portal": {source: payload}, "ocr": {doc_type: ocr_extracted_json},
                 "declarations": {criterion_code: value}, "missing_docs": [doc_type],
                 "employees": int | None}

Comparisons normalise values the way the rule engine does (name token sets, +/-2 points on
local content, compacted identifiers) but are reimplemented here to keep this module standalone.
"""
import math
import re
from datetime import date

NAN = math.nan
_LEGAL_SUFFIXES = {"private", "pvt", "limited", "ltd", "llp", "m/s", "ms", "the"}

# Categorical encodings. "missing" = the source returned nothing (outage / not verified).
STATUS_CODES = {
    "gstn": ["missing", "active", "cancelled", "suspended", "other"],
    "pan": ["missing", "valid", "invalid", "other"],
    "debarment": ["missing", "clear", "debarred", "other"],
    "udyam": ["missing", "valid", "not_found", "other"],
    "startup_india": ["missing", "valid", "expired", "other"],
    "epfo_esic": ["missing", "active", "other"],
}
CATEGORY_CODES = ["none", "Micro", "Small", "Medium", "Large"]
FACTS = [
    "enterprise_category", "local_content_pct", "startup_recognized", "manufacturer_or_trader",
    "gstin", "gst_trade_name", "gst_legal_name", "pan", "udyam_number", "epfo_establishment_code",
    "dpiit_number",
]
_UDYAM_DOCS = ("UDYAM_CERTIFICATE", "EMD_EXEMPTION_PROOF")

FEATURE_NAMES = (
    ["tender_msme_reserved", "tender_mii_threshold", "tender_epfo_applicable", "tender_n_mandatory_docs"]
    + [f"{source}_status" for source in STATUS_CODES]
    + ["udyam_category", "mii_verified_pct", "mii_gap_to_threshold", "declared_pct", "document_pct",
       "declared_minus_verified_pct", "document_minus_verified_pct", "employees_declared",
       "epfo_registered", "employee_ratio", "n_missing_mandatory_docs", "missing_exemption_proof",
       "n_uploaded_docs", "n_unreadable_docs", "n_declarations"]
    + [f"match_{fact}" for fact in FACTS]
    + ["n_mismatches", "n_comparisons"]
)
CATEGORICAL_FEATURES = [f"{source}_status" for source in STATUS_CODES] + ["udyam_category"]


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return NAN


def _code(options: list[str], value) -> int:
    if value is None:
        return 0
    return options.index(value) if value in options else len(options) - 1


def _fields(observed: dict, *doc_types: str) -> dict:
    for doc_type in doc_types:
        doc = observed["ocr"].get(doc_type) or {}
        if doc.get("status") == "extracted":
            return doc.get("fields") or {}
    return {}


def _tokens(value) -> frozenset | None:
    toks = frozenset(re.findall(r"[a-z0-9]+", str(value).casefold().replace("&", " and "))) - _LEGAL_SUFFIXES
    return toks or None


def _compact(value) -> str | None:
    return re.sub(r"\s", "", str(value)).upper() or None


def _roles(value) -> frozenset | None:
    text = str(value).casefold()
    if not text.strip():
        return None
    roles = {r for r, stem in (("manufacturer", "manufactur"), ("trader", "trad")) if stem in text}
    return frozenset(roles or {"other"})


def _recognized(value) -> bool | None:
    return None if value is None else str(value).casefold() in ("valid", "active", "recognized")


def _still_valid(value) -> bool | None:
    try:
        return date.fromisoformat(str(value)) >= date.today()
    except ValueError:
        return None


def _agree(values: list, equal) -> int:
    """1 all available sources agree, 0 some pair disagrees, -1 fewer than two sources."""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return -1
    return int(all(equal(a, b) for i, a in enumerate(present) for b in present[i + 1:]))


def fact_matches(observed: dict) -> dict[str, int]:
    p, d = observed["portal"], observed["declarations"]
    udyam_doc = _fields(observed, *_UDYAM_DOCS)
    gst_doc = _fields(observed, "GST_CERTIFICATE")
    mii_doc = _fields(observed, "MII_LOCAL_CONTENT_SELF_CERTIFICATE")
    startup_doc = _fields(observed, "STARTUP_EMD_EXEMPTION_PROOF")
    get = lambda source, key: (p.get(source) or {}).get(key)  # noqa: E731
    casefold = lambda v: None if v is None else str(v).casefold()  # noqa: E731
    pct = lambda v: None if math.isnan(_num(v)) else _num(v)  # noqa: E731
    declared_role = {"manufacturer": frozenset({"manufacturer"}), "trader": frozenset({"trader"}),
                     "trading": frozenset({"trader"})}.get(str(d.get("manufacturer_or_trader_self_declared", "")).casefold())
    same = lambda a, b: a == b  # noqa: E731

    return {
        "enterprise_category": _agree([casefold(d.get("enterprise_category_self_declared")),
                                       casefold(udyam_doc.get("enterprise_category")),
                                       casefold(get("udyam", "category"))], same),
        "local_content_pct": _agree([pct(d.get("local_content_pct_self_declared")), pct(mii_doc.get("local_content_pct")),
                                     pct(get("mii_local_content", "verified_pct_estimate"))],
                                    lambda a, b: abs(a - b) <= 2.0),
        "startup_recognized": _agree([None if "startup_status_self_declared" not in d
                                      else "recognized" in str(d["startup_status_self_declared"]).casefold(),
                                      _still_valid(startup_doc.get("valid_until")) if startup_doc.get("valid_until") else None,
                                      _recognized(get("startup_india", "status"))], same),
        "manufacturer_or_trader": _agree([declared_role, _roles(udyam_doc["activity"]) if udyam_doc.get("activity") else None,
                                          _roles(get("udyam", "activity")) if get("udyam", "activity") else None],
                                         lambda a, b: bool(a & b)),
        "gstin": _agree([_compact(gst_doc["gstin"]) if gst_doc.get("gstin") else None,
                         _compact(get("gstn", "gstin")) if get("gstn", "gstin") else None], same),
        "gst_trade_name": _agree([_tokens(gst_doc["trade_name"]) if gst_doc.get("trade_name") else None,
                                  _tokens(get("gstn", "trade_name")) if get("gstn", "trade_name") else None], same),
        "gst_legal_name": _agree([_tokens(gst_doc["legal_name"]) if gst_doc.get("legal_name") else None,
                                  _tokens(get("gstn", "legal_name")) if get("gstn", "legal_name") else None], same),
        "pan": _agree([_compact(_fields(observed, "PAN_CARD")["pan"]) if _fields(observed, "PAN_CARD").get("pan") else None,
                       _compact(get("pan", "pan")) if get("pan", "pan") else None], same),
        "udyam_number": _agree([_compact(udyam_doc["udyam_number"]) if udyam_doc.get("udyam_number") else None,
                                _compact(get("udyam", "registration_number")) if get("udyam", "registration_number") else None], same),
        "epfo_establishment_code": _agree(
            [_compact(_fields(observed, "EPFO_ESIC_COMPLIANCE_CERTIFICATE").get("establishment_code") or "") ,
             _compact(get("epfo_esic", "establishment_code") or "")], same),
        "dpiit_number": _agree([_compact(startup_doc["dpiit_number"]) if startup_doc.get("dpiit_number") else None,
                                _compact(get("startup_india", "recognition_number")) if get("startup_india", "recognition_number") else None], same),
    }


def featurize(tender: dict, observed: dict) -> list[float]:
    portal, declared = observed["portal"], observed["declarations"]
    threshold = _num(tender.get("mii_threshold")) or 0.0
    verified = _num((portal.get("mii_local_content") or {}).get("verified_pct_estimate"))
    declared_pct = _num(declared.get("local_content_pct_self_declared"))
    document_pct = _num(_fields(observed, "MII_LOCAL_CONTENT_SELF_CERTIFICATE").get("local_content_pct"))
    employees = _num(observed.get("employees"))
    registered = _num((portal.get("epfo_esic") or {}).get("registered_employee_count"))
    udyam = portal.get("udyam") or {}
    matches = fact_matches(observed)

    row = [
        float(bool(tender.get("msme_reserved"))),
        threshold,
        float(bool(tender.get("epfo_applicable"))),
        float(len(tender.get("mandatory_docs", []))),
        *[float(_code(options, (portal.get(source) or {}).get("status"))) for source, options in STATUS_CODES.items()],
        float(_code(CATEGORY_CODES, udyam.get("category") or ("none" if udyam else None))),
        verified,
        verified - threshold if threshold else NAN,
        declared_pct,
        document_pct,
        declared_pct - verified,
        document_pct - verified,
        employees,
        registered,
        registered / employees if employees and not math.isnan(registered) else NAN,
        float(len(observed.get("missing_docs", []))),
        float("EMD_EXEMPTION_PROOF" in observed.get("missing_docs", [])),
        float(len(observed["ocr"])),
        float(sum(1 for doc in observed["ocr"].values() if doc.get("status") not in (None, "extracted"))),
        float(len(declared)),
        *[float(matches[fact]) for fact in FACTS],
        float(sum(1 for v in matches.values() if v == 0)),
        float(sum(1 for v in matches.values() if v >= 0)),
    ]
    assert len(row) == len(FEATURE_NAMES)
    return row
