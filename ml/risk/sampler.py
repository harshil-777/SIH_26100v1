"""Synthetic bids: a *true* state of the bidder, and what the pipeline would *observe* of it.

A bid is a plain dict in the same shapes the rule engine consumes (portal payloads like the
mock registry's, OCR results like documents.ocr_extracted_json, declarations by
criterion_code), so it can be scored by the real app code and featurised without it.

Problems are drawn independently, so realistic combinations occur (a debarred bidder who also
inflated local content). Observation noise -- a portal outage, an unreadable scan, a field OCR
missed, a declaration left blank -- is applied on top of the truth, never instead of it.
"""
import copy
import random
from datetime import date, timedelta

from ml.common.entities import Company, random_company, variant_name

_GOODS_DOCS = ["MII_LOCAL_CONTENT_SELF_CERTIFICATE", "QUALITY_BIS_CERTIFICATE", "TURNOVER_CERTIFICATE_CA"]
_SERVICE_DOCS = ["PAST_EXPERIENCE_PROOF", "EPFO_ESIC_COMPLIANCE_CERTIFICATE", "TURNOVER_CERTIFICATE_CA", "PSARA_LICENSE"]
_OCR_CONFUSIONS = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B"}


def sample_tender(rng: random.Random) -> dict:
    goods = rng.random() < 0.55
    msme_reserved = rng.random() < 0.45
    mii_threshold = rng.choice([20, 25, 40, 50, 50, 60]) if goods and rng.random() < 0.8 else 0
    pool = _GOODS_DOCS if goods else _SERVICE_DOCS
    required = rng.sample(pool, rng.randint(1, len(pool)))
    if mii_threshold and "MII_LOCAL_CONTENT_SELF_CERTIFICATE" not in required:
        required.append("MII_LOCAL_CONTENT_SELF_CERTIFICATE")
    requires_oem = goods and rng.random() < 0.3
    if requires_oem:
        required.append("OEM_AUTHORIZATION_LETTER")
    if msme_reserved:
        required.append("EMD_EXEMPTION_PROOF")
    return {
        "category": "Goods" if goods else "Services",
        "msme_reserved": msme_reserved,
        "mii_threshold": mii_threshold,
        "epfo_applicable": rng.random() < 0.8,
        "requires_oem": requires_oem,
        "mandatory_docs": required,
    }


def _truth(rng: random.Random, tender: dict) -> tuple[Company, dict]:
    company = random_company(rng)
    t: dict = {
        "gst_status": rng.choices(["active", "cancelled", "suspended"], weights=[88, 7, 5])[0],
        "pan_status": "valid" if rng.random() < 0.95 else "invalid",
        "debarred": rng.random() < 0.04,
        "startup": None,
        "declared_category": company.category,
        "declared_role": None,
        "trade_name_on_doc": company.trade_name,
        "gstin_on_doc": company.gstin,
        "declared_employees": company.employee_count,
        "epfo_registered": company.employee_count,
        "missing_docs": [d for d in tender["mandatory_docs"] if rng.random() < 0.025],
    }
    if company.category != "Large" and rng.random() < 0.2:
        # Self-declared a different MSME category than Udyam records (e.g. Small vs Medium).
        t["declared_category"] = rng.choice([c for c in ("Micro", "Small", "Medium") if c != company.category])
    if rng.random() < 0.10:
        t["startup"] = {"status": "valid" if rng.random() < 0.7 else "expired"}
    if tender["msme_reserved"] and tender["category"] == "Goods":
        t["declared_role"] = "Manufacturer"
        if company.activity_role == "trader" and rng.random() < 0.5:
            t["declared_role"] = "Manufacturer"  # a trader claiming manufacturer status
        elif company.activity_role != "manufacturer":
            t["declared_role"] = None
    if rng.random() < 0.15:
        t["trade_name_on_doc"] = variant_name(rng, company.trade_name)
    if rng.random() < 0.03:
        t["gstin_on_doc"] = company.gstin[:-3] + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(3))
    if rng.random() < 0.22:
        # Declared headcount inflated relative to the EPFO record.
        t["epfo_registered"] = max(1, int(company.employee_count * rng.uniform(0.2, 0.8)))
    if tender["mii_threshold"]:
        truth_pct = round(min(95, max(5, rng.gauss(tender["mii_threshold"] + 4, 18))))
        t["local_content"] = truth_pct
        t["declared_local_content"] = truth_pct if rng.random() < 0.7 else min(99, truth_pct + rng.randint(5, 20))
        t["doc_local_content"] = t["declared_local_content"] if rng.random() < 0.3 else truth_pct
    return company, t


def _portals(company: Company, t: dict, tender: dict) -> dict:
    portals = {
        "gstn": {"status": t["gst_status"], "gstin": company.gstin, "legal_name": company.legal_name,
                 "trade_name": company.trade_name},
        "pan": {"status": t["pan_status"], "pan": company.pan},
        "debarment": {"status": "debarred" if t["debarred"] else "clear"},
        "epfo_esic": {"status": "active", "registered_employee_count": t["epfo_registered"],
                      "establishment_code": company.establishment_code},
    }
    if company.category == "Large":
        portals["udyam"] = {"status": "not_found"}
    else:
        portals["udyam"] = {"status": "valid", "category": company.category,
                            "registration_number": company.udyam_number, "activity": company.activity}
    if t["startup"]:
        portals["startup_india"] = {"status": t["startup"]["status"], "recognition_number": company.dpiit_number}
    if tender["mii_threshold"]:
        portals["mii_local_content"] = {"declared_pct": t["declared_local_content"],
                                        "verified_pct_estimate": t["local_content"]}
    return portals


def _uploads(rng: random.Random, company: Company, t: dict, tender: dict) -> dict:
    """Documents the bidder uploaded, as perfectly extracted OCR results."""
    docs: dict[str, dict] = {}

    def add(doc_type: str, fields: dict) -> None:
        if doc_type not in t["missing_docs"]:
            docs[doc_type] = {"status": "extracted", "fields": fields}

    if rng.random() < 0.6:
        add("GST_CERTIFICATE", {"gstin": t["gstin_on_doc"], "trade_name": t["trade_name_on_doc"],
                                "legal_name": company.legal_name})
    if rng.random() < 0.35:
        add("PAN_CARD", {"pan": company.pan, "legal_name": company.legal_name})
    if company.category != "Large" and ("EMD_EXEMPTION_PROOF" in tender["mandatory_docs"] or rng.random() < 0.3):
        add("EMD_EXEMPTION_PROOF", {"udyam_number": company.udyam_number, "enterprise_category": company.category,
                                    "activity": company.activity, "legal_name": company.legal_name})
    if tender["mii_threshold"]:
        add("MII_LOCAL_CONTENT_SELF_CERTIFICATE", {"local_content_pct": float(t["doc_local_content"]),
                                                   "gstin": company.gstin})
    if "EPFO_ESIC_COMPLIANCE_CERTIFICATE" in tender["mandatory_docs"]:
        add("EPFO_ESIC_COMPLIANCE_CERTIFICATE", {"establishment_code": company.establishment_code,
                                                 "legal_name": company.legal_name})
    if t["startup"]:
        valid_until = date.today() + timedelta(days=rng.randint(60, 2000))
        if t["startup"]["status"] == "expired":
            valid_until = date.today() - timedelta(days=rng.randint(30, 900))
        add("STARTUP_EMD_EXEMPTION_PROOF", {"dpiit_number": company.dpiit_number, "valid_until": valid_until.isoformat()})
    for doc_type in tender["mandatory_docs"]:
        if doc_type not in docs:
            add(doc_type, {"legal_name": company.legal_name})
    return docs


def _declarations(company: Company, t: dict, tender: dict) -> dict:
    declared = {}
    if company.category != "Large":
        declared["enterprise_category_self_declared"] = t["declared_category"]
    if tender["mii_threshold"]:
        declared["local_content_pct_self_declared"] = str(t["declared_local_content"])
    if t["startup"]:
        declared["startup_status_self_declared"] = "Recognized Startup"
    if t["declared_role"]:
        declared["manufacturer_or_trader_self_declared"] = t["declared_role"]
    return declared


def _missing_mandatory(tender: dict, uploads: dict, t: dict) -> list[str]:
    missing = list(t["missing_docs"])
    # A bidder without an Udyam record simply has no MSE exemption proof to upload.
    if "EMD_EXEMPTION_PROOF" in tender["mandatory_docs"] and "EMD_EXEMPTION_PROOF" not in uploads:
        missing.append("EMD_EXEMPTION_PROOF")
    return sorted(set(missing))


def _observe(rng: random.Random, bid: dict) -> dict:
    """What the pipeline would actually see: the truth plus outages and extraction errors."""
    seen = copy.deepcopy(bid)
    for source in list(seen["portal"]):
        if rng.random() < 0.04:
            del seen["portal"][source]  # portal outage / timeout: no verification result
    for doc in seen["ocr"].values():
        roll = rng.random()
        if roll < 0.03:
            doc.update(status="failed", fields={})
        elif roll < 0.05:
            doc.update(status="no_text", fields={})
        else:
            for field in list(doc["fields"]):
                if rng.random() < 0.06:
                    del doc["fields"][field]  # OCR missed the field
                elif rng.random() < 0.02 and isinstance(doc["fields"][field], str):
                    doc["fields"][field] = "".join(
                        _OCR_CONFUSIONS.get(ch, ch) if rng.random() < 0.15 else ch for ch in doc["fields"][field]
                    )
    for code in list(seen["declarations"]):
        if rng.random() < 0.05:
            del seen["declarations"][code]  # proforma field left blank
    return seen


def sample_bid(rng: random.Random) -> dict:
    """{"tender", "truth": bid, "observed": bid} where bid = portal/ocr/declarations/missing_docs/employees."""
    tender = sample_tender(rng)
    company, t = _truth(rng, tender)
    uploads = _uploads(rng, company, t, tender)
    truth = {
        "portal": _portals(company, t, tender),
        "ocr": uploads,
        "declarations": _declarations(company, t, tender),
        "missing_docs": _missing_mandatory(tender, uploads, t),
        "employees": t["declared_employees"],
    }
    return {"tender": tender, "truth": truth, "observed": _observe(rng, truth)}
