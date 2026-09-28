"""Reference recommendations the model is trained to write.

Varied phrasing per finding, each carrying the concrete values and a sensible next step, in
severity order, ending with one of the three verdict sentences the rest of the system expects
("Recommend qualifying", "Recommend disqualification", "Recommend officer review before
qualifying"). Every finding's KEYWORDS phrase appears in its sentence and nowhere else.
"""
import random

from ml.recommendation.findings import MANDATORY_TYPES, finding_key, verdict

PREFIX = "AI-generated, advisory only: "

_FACT_WORDS = {
    "mismatch:gstin": "GSTIN",
    "mismatch:gst_legal_name": "legal name",
    "mismatch:pan": "PAN card",
    "mismatch:udyam_number": "Udyam registration number",
    "mismatch:epfo_establishment_code": "EPFO establishment code",
    "mismatch:dpiit_number": "DPIIT recognition number",
}


# Neutral names for unreadable documents, so e.g. an unreadable PAN card doesn't print "PAN card"
# (the PAN-mismatch keyword) and read as a finding that doesn't exist.
_DOC_NAMES = {
    "PAN_CARD": "PAN document",
    "STARTUP_EMD_EXEMPTION_PROOF": "recognition certificate",
    "MII_LOCAL_CONTENT_SELF_CERTIFICATE": "Make in India self-certificate",
    "EPFO_ESIC_COMPLIANCE_CERTIFICATE": "EPFO/ESIC certificate",
    "EMD_EXEMPTION_PROOF": "EMD exemption proof",
}


def _q(value) -> str:
    return f"'{value}'" if value not in (None, "") else "not stated"


def _sentence(rng: random.Random, f: dict) -> str:
    key, t = finding_key(f), f["type"]
    pick = rng.choice
    if t == "gst_inactive":
        return pick([
            f"The GST registration is {f['status']} on the GSTN portal, so the bidder cannot lawfully supply against this tender.",
            f"GSTN reports the GST registration as {f['status']}; an active registration is mandatory.",
        ])
    if t == "debarred":
        return pick([
            "The bidder appears on the debarment registry and cannot be awarded a contract while the order is in force.",
            "A current debarment order is recorded against this bidder.",
        ])
    if t == "pan_invalid":
        return pick([
            f"PAN verification returned '{f['status']}', so the bidder's identity for income-tax purposes is not established.",
            f"The PAN verification result is '{f['status']}' rather than valid.",
        ])
    if t == "missing_documents":
        docs = ", ".join(f["documents"])
        return pick([
            f"Mandatory document(s) missing from the bid: {docs}.",
            f"The bid is missing the following mandatory document(s): {docs}.",
        ])
    if t == "msme_ineligible":
        return pick([
            f"The tender is reserved for MSEs, but the bidder's Udyam classification is {f['category']}.",
            f"This is an MSE-reserved tender and the bidder ({f['category']}) does not qualify for the reservation.",
        ])
    if t == "local_content_shortfall":
        return pick([
            f"Verified local content of {f['verified']}% is below the required {f['threshold']}%.",
            f"At {f['verified']}%, the verified local content is below the required {f['threshold']}% for this tender.",
        ])
    if t == "local_content_unverified":
        return pick([
            "The local content claim could not be verified against the portal; ask for supporting cost details.",
            "Local content could not be verified independently.",
        ])
    if t == "epfo_mismatch":
        return pick([
            f"The declared headcount ({f['declared']}) does not match EPFO records ({f['registered']}); request recent ECR challans to confirm.",
            f"EPFO records show {f['registered']} registered employees against {f['declared']} declared.",
        ])
    if t == "epfo_unverified":
        return pick([
            "EPFO data was unavailable, so the declared headcount is unconfirmed.",
            "The EPFO data could not be retrieved to confirm the declared headcount.",
        ])
    if t == "unreadable":
        doc = _DOC_NAMES.get(f["document"], f["document"].replace("_", " ").lower())
        return pick([
            f"The uploaded {doc} could not be read; ask the bidder for a legible copy.",
            f"Request a legible copy of the {doc}, which could not be read.",
        ])
    if key == "mismatch:enterprise_category":
        return pick([
            f"The declared enterprise category ({_q(f['declared'])}) conflicts with Udyam ({_q(f['portal'])}).",
            f"The enterprise category does not agree across sources (declared {_q(f['declared'])}, Udyam {_q(f['portal'])}).",
        ])
    if key == "mismatch:local_content_pct":
        return pick([
            f"The local content figures disagree: declared {_q(f['declared'])}, certificate {_q(f['document'])}, portal estimate {_q(f['portal'])}.",
            "The declared, certified and verified local content figures do not agree.",
        ])
    if key == "mismatch:startup_recognized":
        return pick([
            "Startup recognition is claimed but is not currently valid, so startup relaxations should not be applied.",
            "The claimed startup status could not be confirmed as current.",
        ])
    if key == "mismatch:manufacturer_or_trader":
        return pick([
            f"The bidder declared itself a manufacturer, but Udyam records its activity as {_q(f['portal'])}.",
            "The declared manufacturer status is not supported by the Udyam activity record.",
        ])
    if key == "mismatch:gst_trade_name":
        return pick([
            f"The trade name on the uploaded certificate ({_q(f['document'])}) differs from the GSTN record ({_q(f['portal'])}); request a current certificate.",
            "The certificate's trade name does not match the GSTN record, which may indicate an outdated or altered document.",
        ])
    word = _FACT_WORDS.get(key, "a detail")
    return pick([
        f"The {word} on the uploaded document does not match the portal record.",
        f"There is a mismatch in the {word} between the document and the portal.",
    ])


def write_target(rng: random.Random, overall_score, risk_level: str, findings: list[dict]) -> str:
    score = f"{float(overall_score):.1f}"
    opening = rng.choice([
        f"Score {score}/100 ({risk_level} risk).",
        f"This bid scores {score}/100 and is rated {risk_level} risk.",
        f"Compliance score {score}/100, {risk_level} risk.",
    ])
    ordered = sorted(findings, key=lambda f: (f["type"] not in MANDATORY_TYPES, f["type"] == "unreadable"))
    body = " ".join(_sentence(rng, f) for f in ordered)
    if not findings:
        body = rng.choice([
            "All mandatory checks passed and every document is consistent with the verified portal records.",
            "Every statutory check passed and the submitted documents agree with the portal records.",
        ])
    closing = {
        "disqualify": rng.choice(["Recommend disqualification, subject to officer review.",
                                  "Recommend disqualification; the officer should confirm before recording the decision."]),
        "qualify": rng.choice(["Recommend qualifying, subject to officer review.",
                               "Recommend qualifying; no follow-up is needed."]),
        "review": rng.choice(["Recommend officer review before qualifying.",
                              "Recommend officer review before qualifying, once the points above are resolved."]),
    }[verdict(risk_level, findings)]
    return f"{PREFIX}{opening} {body} {closing}"
