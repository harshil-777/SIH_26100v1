"""Generate a larger, varied set of demo bids for every seeded tender.

    python scripts/generate_demo_bids.py

Writes WORKING DOCUMENTS/demo_bids/ -- bidders, document submissions, declarations and the mock
government-portal responses for each new bidder, in the same shapes as the base fixtures. Nothing
here decides a bid's score: each bidder gets a realistic identity plus zero or more real-world
defects (a cancelled GSTIN, a missing annexure, an EPFO headcount gap, a category mismatch ...),
and the app's own rule engine scores them once loaded (python -m app.db.seed_demo).

Deterministic (fixed seed), so regenerating produces the same bidders. All identities are
fictitious and only follow the public *format* of PAN / GSTIN / Udyam / CIN / EPFO codes.
"""
import csv
import json
import random
import string
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "WORKING DOCUMENTS"
OUT = BASE / "demo_bids"

# Bids per tender *including* the base fixture's own bidders, so tenders end up differently sized.
TARGET_BIDS = {"T2026-0001": 14, "T2026-0002": 9, "T2026-0003": 12, "T2026-0004": 13, "T2026-0005": 10, "T2026-0006": 11}

STATES = {
    "Maharashtra": ("27", "MH", ["MUM", "PUN", "NAG"]),
    "Karnataka": ("29", "KA", ["BLR", "MYS"]),
    "Delhi": ("07", "DL", ["SDL", "NDL"]),
    "Gujarat": ("24", "GJ", ["AMD", "SRT"]),
    "Tamil Nadu": ("33", "TN", ["CHE", "CBE"]),
    "Uttar Pradesh": ("09", "UP", ["LKO", "NOI"]),
    "Telangana": ("36", "TG", ["HYD"]),
    "West Bengal": ("19", "WB", ["KOL"]),
    "Haryana": ("06", "HR", ["GGN", "FBD"]),
    "Rajasthan": ("08", "RJ", ["JPR"]),
    "Kerala": ("32", "KL", ["TVM", "KOC"]),
    "Madhya Pradesh": ("23", "MP", ["BPL", "IND"]),
}

# Per tender: name stems, suffixes and the Udyam activity line that fits the goods/services bought.
TRADES = {
    "T2026-0001": (
        ["Vertex", "Infosys Hardware", "Pinnacle", "Zenith", "Quantum", "Apex", "Silicon Bay", "Nexgen", "Tridev", "Orbit", "Shakti", "Keystone", "Bluechip"],
        ["Computers Pvt Ltd", "Infotech Pvt Ltd", "IT Solutions LLP", "Systems Pvt Ltd", "Technologies"],
        "Manufacturing - Computer Hardware",
    ),
    "T2026-0002": (
        ["Coolair", "Himalaya", "Arctic", "Polar", "Breeze", "Climatech", "Frostline", "Sheetal", "Aircare"],
        ["Engineers", "HVAC Services", "Facility Services Pvt Ltd", "Aircon Services LLP"],
        "Services - Repair and Maintenance",
    ),
    "T2026-0003": (
        ["Godavari", "Ironwood", "Steelcraft", "Durafab", "Mahalaxmi", "Rathore", "Vishwakarma", "Metalform", "Sturdy"],
        ["Furniture Works", "Steel Industries", "Fabricators Pvt Ltd", "Interiors LLP"],
        "Manufacturing - Furniture",
    ),
    "T2026-0004": (
        ["Talentbridge", "Workforce", "Skillnet", "Peopleline", "Hirewell", "Codecraft", "Staffmart", "Infohire", "Brightpath", "Techforce"],
        ["Services Pvt Ltd", "Consultants", "Staffing Solutions LLP", "HR Services"],
        "Services - IT and Manpower",
    ),
    "T2026-0005": (
        ["Suryoday", "Helios", "Sunshakti", "Greenray", "Tejas", "Ujjwal", "Prakash", "Savitr", "Brightsun"],
        ["Solar Pvt Ltd", "Renewables", "Energy Systems LLP", "Green Energy"],
        "Manufacturing - Solar Thermal Equipment",
    ),
    "T2026-0006": (
        ["Rakshak", "Sentinel", "Vigilant", "Garuda", "Shield", "Prahari", "Suraksha", "Eagle Eye", "Fortress", "Kavach"],
        ["Security Services", "Security Agency Pvt Ltd", "Guarding Solutions", "Protection Services LLP"],
        "Services - Security and Investigation",
    ),
}

# Defects a bid can carry; weights tuned so each tender gets a spread from clean to non-compliant.
DEFECTS = [
    ("gst_cancelled", 5),
    ("gst_suspended", 3),
    ("pan_invalid", 4),
    ("debarred", 3),
    ("missing_mandatory_doc", 7),
    ("category_mismatch", 8),
    ("local_content_short", 9),
    ("epfo_mismatch", 12),
    ("gst_name_mismatch", 7),
    ("not_msme", 5),
]


def read_csv(name: str) -> list[dict[str, str]]:
    with (BASE / name).open(encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row and not next(iter(row.values()), "").startswith("#")]


def letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def pick_defects(rng: random.Random, tender: dict) -> list[str]:
    """0 defects about 40% of the time, else 1 (sometimes 2), limited to ones that can apply."""
    applicable = [
        (name, weight)
        for name, weight in DEFECTS
        if not (name == "local_content_short" and float(tender["mii_local_content_threshold_pct"] or 0) <= 0)
        and not (name == "not_msme" and tender["msme_reserved"] != "TRUE")
    ]
    roll = rng.random()
    count = 0 if roll < 0.40 else 1 if roll < 0.85 else 2
    chosen: list[str] = []
    while len(chosen) < count:
        name = rng.choices([n for n, _ in applicable], weights=[w for _, w in applicable])[0]
        if name not in chosen:
            chosen.append(name)
    return chosen


def make_bidder(rng: random.Random, index: int, tender: dict, requirements: list[dict], used_names: set[str]):
    tender_id = tender["tender_id"]
    stems, suffixes, activity = TRADES[tender_id]
    while True:
        name = f"{rng.choice(stems)} {rng.choice(suffixes)}"
        if name not in used_names:
            used_names.add(name)
            break
    bidder_id = f"G{index:03d}"
    bid_id = f"BID-{bidder_id}-{tender_id}"
    defects = pick_defects(rng, tender)

    state = rng.choice(list(STATES))
    state_code, st, districts = STATES[state]
    entity = "C" if "Pvt Ltd" in name else "F" if "LLP" in name else "P"
    pan = f"{letters(rng, 3)}{entity}{name[0]}{digits(rng, 4)}{rng.choice(string.ascii_uppercase)}"
    gstin = f"{state_code}{pan}1Z{rng.choice(string.digits + string.ascii_uppercase)}"

    msme = tender["msme_reserved"] == "TRUE"
    if "not_msme" in defects:
        category, employees = "Large", rng.randint(260, 900)
    elif msme:
        category = rng.choices(["Micro", "Small"], weights=[1, 3])[0]
        employees = rng.randint(8, 19) if category == "Micro" else rng.randint(20, 150)
    else:
        category = rng.choices(["Micro", "Small", "Medium"], weights=[1, 3, 2])[0]
        employees = {"Micro": rng.randint(8, 19), "Small": rng.randint(20, 150), "Medium": rng.randint(120, 400)}[category]
    udyam_number = None if category == "Large" else f"UDYAM-{st}-{digits(rng, 2)}-{digits(rng, 7)}"
    year = rng.randint(2005, 2021)
    cin = f"U{digits(rng, 5)}{st}{year}PTC{digits(rng, 6)}" if entity == "C" else None
    epfo_code = f"{st}/{rng.choice(districts)}/{digits(rng, 7)}/000"

    threshold = float(tender["mii_local_content_threshold_pct"] or 0)
    local_pct = None
    if threshold > 0:
        local_pct = rng.randint(int(threshold * 0.55), int(threshold * 0.92)) if "local_content_short" in defects else rng.randint(int(threshold), min(95, int(threshold) + 30))

    verified = "2026-09-{:02d}T{:02d}:{:02d}:{:02d}Z".format(rng.randint(18, 28), rng.randint(9, 17), rng.randint(0, 59), rng.randint(0, 59))
    legal_name = name.replace("Pvt Ltd", "Private Limited")

    portal: dict = {
        "bidder_id": bidder_id,
        "udyam": (
            {"status": "not_found", "note": "Large enterprise - not Udyam-eligible"}
            if category == "Large"
            else {
                "status": "valid",
                "registration_number": udyam_number,
                "category": "Medium" if "category_mismatch" in defects and category != "Medium" else category,
                "activity": activity,
                "date_of_registration": f"{rng.randint(2018, 2023)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "confidence": round(rng.uniform(0.94, 0.99), 2),
                "verified_at": verified,
            }
        ),
        "gstn": {
            "status": "cancelled" if "gst_cancelled" in defects else "suspended" if "gst_suspended" in defects else "active",
            "gstin": gstin,
            "legal_name": legal_name,
            "trade_name": name.replace(" Pvt Ltd", "").replace(" LLP", ""),
            "return_filing_status": "not_filed" if {"gst_cancelled", "gst_suspended"} & set(defects) else "up_to_date",
            "last_return_period": "2025-11" if {"gst_cancelled", "gst_suspended"} & set(defects) else "2026-08",
            "confidence": round(rng.uniform(0.95, 0.99), 2),
            "verified_at": verified,
        },
        "pan": {
            "status": "invalid" if "pan_invalid" in defects else "valid",
            "pan": pan,
            **({"reason": "PAN flagged inoperative by the source registry"} if "pan_invalid" in defects else {"aadhaar_seeding_status": "linked"}),
            "confidence": round(rng.uniform(0.95, 0.99), 2),
            "verified_at": verified,
        },
        "mca21": (
            {"status": "active", "cin": cin, "company_name": legal_name, "company_status": "Active", "confidence": 0.97, "verified_at": verified}
            if cin
            else {"status": "not_applicable"}
        ),
        "epfo_esic": {
            "status": "active",
            "establishment_code": epfo_code,
            "establishment_status": "Active",
            "registered_employee_count": max(1, int(employees * rng.uniform(0.35, 0.85))) if "epfo_mismatch" in defects else employees,
            "confidence": round(rng.uniform(0.88, 0.97), 2),
            "verified_at": verified,
        },
        "startup_india": {"status": "not_applicable"},
        "nsic": {"status": "not_applicable"},
        "debarment": (
            {
                "status": "debarred",
                "list_source": "internal_debarred_entities_registry",
                "order_reference": f"{tender['department'].split()[0].upper()}/DEBAR/2025/{digits(rng, 4)}",
                "debarment_period": "2025-08-01 to 2027-07-31",
                "confidence": 1.0,
                "verified_at": verified,
            }
            if "debarred" in defects
            else {"status": "clear", "list_source": "internal_debarred_entities_registry", "confidence": 1.0, "verified_at": verified}
        ),
        "document_cross_check": [],
    }
    if threshold > 0:
        portal["mii_local_content"] = {
            "declared_pct": local_pct,
            "verified_pct_estimate": local_pct,
            "source": "BIS/DPIIT classification cross-check",
            "confidence": round(rng.uniform(0.85, 0.93), 2),
            "verified_at": verified,
        }
    if "category_mismatch" in defects and category != "Medium":
        portal["document_cross_check"].append(
            {"doc_type": "udyam_certificate", "match": False, "confidence": 0.72,
             "note": f"Certificate category reads Medium; bid form declares {category}"}
        )
    elif udyam_number:
        portal["document_cross_check"].append({"doc_type": "udyam_certificate", "match": True, "confidence": 0.97})
    if "gst_name_mismatch" in defects:
        portal["document_cross_check"].append(
            {"doc_type": "gst_certificate", "match": False, "confidence": 0.45,
             "note": f"Uploaded certificate trade name differs from the GSTN record for {gstin}"}
        )
    else:
        portal["document_cross_check"].append({"doc_type": "gst_certificate", "match": True, "confidence": 0.96})

    submitted_on = date(2026, 9, 10) + timedelta(days=rng.randint(0, 16))
    submissions, declarations = [], []
    mandatory_types = [r["document_type"] for r in requirements if r["mandatory"] == "TRUE"]
    missing = rng.choice(mandatory_types) if "missing_mandatory_doc" in defects and mandatory_types else None
    is_mse = category in {"Micro", "Small"}
    for req in requirements:
        doc_type = req["document_type"]
        if req["mandatory"] != "TRUE" and not (doc_type == "EMD_EXEMPTION_PROOF" and is_mse):
            continue
        ok = doc_type != missing
        submissions.append({
            "bid_id": bid_id, "bidder_id": bidder_id, "tender_id": tender_id, "document_type": doc_type,
            "submitted": "TRUE" if ok else "FALSE",
            "file_ref": f"doc/{bidder_id}/{doc_type.lower()}.pdf" if ok else "",
            "note": "" if ok else f"Not submitted - {req['buyer_label']} is mandatory for this tender",
        })
    submissions.append({
        "bid_id": bid_id, "bidder_id": bidder_id, "tender_id": tender_id, "document_type": "GST_CERTIFICATE",
        "submitted": "TRUE", "file_ref": f"doc/{bidder_id}/gst_certificate.pdf",
        "note": "Trade name on certificate differs from GSTN record" if "gst_name_mismatch" in defects else "",
    })

    if category != "Large":
        declarations.append({"bid_id": bid_id, "bidder_id": bidder_id, "tender_id": tender_id,
                             "criterion_code": "enterprise_category_self_declared", "declared_value": category,
                             "declared_at": submitted_on.isoformat(), "note": ""})
    if local_pct is not None:
        declarations.append({"bid_id": bid_id, "bidder_id": bidder_id, "tender_id": tender_id,
                             "criterion_code": "local_content_pct_self_declared", "declared_value": str(local_pct),
                             "declared_at": submitted_on.isoformat(), "note": ""})

    bidder = {
        "bidder_id": bidder_id, "name": name, "pan": pan, "gstin": gstin, "udyam_number": udyam_number or "",
        "cin": cin or "", "dpiit_recognition_number": "", "nsic_registration_number": "",
        "epfo_establishment_code": epfo_code, "employee_count": str(employees), "enterprise_category": category,
        "declared_local_content_pct": "" if local_pct is None else str(local_pct), "state": state,
        "target_tender_id": tender_id, "defects": "|".join(defects) or "none",
        "submitted_at": f"{submitted_on.isoformat()}T{rng.randint(9, 18):02d}:{rng.randint(0, 59):02d}:00+05:30",
    }
    return bidder, submissions, declarations, portal


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rng = random.Random(2026_09_30)
    tenders = {row["tender_id"]: row for row in read_csv("dummy_tenders.csv")}
    requirements = read_csv("dummy_tender_document_requirements.csv")
    base_counts: dict[str, int] = {}
    for row in read_csv("dummy_bidders.csv"):
        base_counts[row["target_tender_id"]] = base_counts.get(row["target_tender_id"], 0) + 1

    bidders, submissions, declarations, portal = [], [], [], []
    used_names: set[str] = set()
    index = 1
    for tender_id, target in TARGET_BIDS.items():
        reqs = [r for r in requirements if r["tender_id"] == tender_id]
        for _ in range(target - base_counts.get(tender_id, 0)):
            b, s, d, p = make_bidder(rng, index, tenders[tender_id], reqs, used_names)
            bidders.append(b)
            submissions.extend(s)
            declarations.extend(d)
            portal.append(p)
            index += 1

    for i, row in enumerate(submissions, 1):
        row["submission_id"] = f"GS{i:04d}"
    for i, row in enumerate(declarations, 1):
        row["declaration_id"] = f"GD{i:04d}"

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "bidders.csv", bidders)
    write_csv(OUT / "submissions.csv", submissions)
    write_csv(OUT / "declarations.csv", declarations)
    (OUT / "portal_responses.json").write_text(
        json.dumps({"note": "Generated by scripts/generate_demo_bids.py -- fictitious identities.", "bidders": portal}, indent=1),
        encoding="utf-8",
    )
    defect_counts: dict[str, int] = {}
    for b in bidders:
        for d in b["defects"].split("|"):
            defect_counts[d] = defect_counts.get(d, 0) + 1
    print(f"{len(bidders)} bidders, {len(submissions)} submissions, {len(declarations)} declarations -> {OUT}")
    print("defects:", dict(sorted(defect_counts.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
