"""Parsing and derivation for the six seed fixtures (BUILD_SPEC.md section 4).

Deliberately free of SQLAlchemy imports: everything here is pure so the derived bid IDs,
document-type set and rule blobs can be checked without a database.
"""
import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ADAPTER_SOURCES = (
    "udyam",
    "gstn",
    "pan",
    "mca21",
    "epfo_esic",
    "startup_india",
    "nsic",
    "debarment",
    "mii_local_content",
)

# Codes named in BUILD_SPEC section 3 that no fixture row exercises yet. The Phase 1
# cross-check stage refers to them and documents.doc_type has an FK onto this table.
SPEC_EXTRA_DOCUMENT_TYPES = ("PAN_CARD", "UDYAM_CERTIFICATE")

DOCUMENT_TYPE_DISPLAY_NAMES = {
    "OEM_AUTHORIZATION_LETTER": "OEM Authorization Letter",
    "MII_LOCAL_CONTENT_SELF_CERTIFICATE": "Make in India Local Content Self-Certificate",
    "TURNOVER_CERTIFICATE_CA": "CA-Certified Turnover Certificate",
    "EMD_EXEMPTION_PROOF": "EMD Exemption Proof",
    "PAST_EXPERIENCE_PROOF": "Past Experience Proof",
    "EPFO_ESIC_COMPLIANCE_CERTIFICATE": "EPFO/ESIC Compliance Certificate",
    "QUALITY_BIS_CERTIFICATE": "BIS Quality Certificate",
    "PSARA_LICENSE": "PSARA License",
    "GST_CERTIFICATE": "GST Registration Certificate",
    "STARTUP_EMD_EXEMPTION_PROOF": "Startup (DPIIT) EMD Exemption Proof",
    "PAN_CARD": "PAN Card",
    "UDYAM_CERTIFICATE": "Udyam Registration Certificate",
}

# Fictional rows beyond the one derived from B005, so the debarment adapter in Phase 1 is
# not trivially a single-row lookup.
EXTRA_DEBARRED_ENTITIES = (
    {
        "pan": "AAXCV9876P",
        "gstin": "19AAXCV9876P1Z4",
        "name": "Eastern Infra Projects Pvt Ltd",
        "order_reference": "NIC/DEBAR/2024/0037",
        "debarred_from": date(2024, 9, 1),
        "debarred_until": date(2026, 8, 31),
        "list_source": "internal_debarred_entities_registry",
    },
    {
        "pan": "BBQWE1122L",
        "gstin": "36BBQWE1122L1Z9",
        "name": "Deccan Office Supplies",
        "order_reference": "CPWD/DEBAR/2025/0014",
        "debarred_from": date(2025, 2, 15),
        "debarred_until": date(2028, 2, 14),
        "list_source": "internal_debarred_entities_registry",
    },
    {
        "pan": "CCZXC3344M",
        "gstin": None,
        "name": "Himalaya Facility Management LLP",
        "order_reference": "RLY/DEBAR/2023/0102",
        "debarred_from": date(2023, 11, 20),
        "debarred_until": date(2026, 11, 19),
        "list_source": "internal_debarred_entities_registry",
    },
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a fixture CSV, dropping the trailing `#` comment block and blank lines."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        first_field = reader.fieldnames[0]
        return [
            row
            for row in reader
            if (row.get(first_field) or "").strip()
            and not row[first_field].lstrip().startswith("#")
        ]


def as_bool(value: str | None) -> bool:
    return (value or "").strip().upper() == "TRUE"


def as_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def as_decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    return Decimal(value) if value else None


def as_text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def as_date(value: str | None) -> date | None:
    """asyncpg binds DATE columns strictly -- fixture strings must become date objects."""
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def as_utc_datetime(value: str | None) -> datetime | None:
    """Fixture dates land in TIMESTAMPTZ columns; read bare dates as UTC midnight."""
    value = (value or "").strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_eligibility_rules_typed(
    *,
    msme_reserved: bool,
    mii_local_content_threshold_pct: Decimal | None,
    epfo_applicable_employee_threshold: int | None,
) -> dict[str, Any]:
    """Derive the section 8 criteria blob from a tender's own policy flags.

    The 4 mandatory criteria are constant (BUILD_SPEC.md section 8's literal example), plus
    msme_eligibility as a 5th mandatory one on MSME-reserved tenders. The graded set is
    switched on by the MII threshold / EPFO threshold.

    OEM authorization is deliberately not a separate graded criterion: every tender that
    sets requires_oem_authorization also seeds OEM_AUTHORIZATION_LETTER as a *mandatory*
    tender_document_requirements row, so document_completeness already owns that signal.
    A parallel graded criterion would just be a redundant, perfectly-correlated copy of it.
    """
    criteria: list[dict[str, Any]] = [
        {
            "id": "gst_active",
            "type": "mandatory",
            "source": "verification_results.gstn.status==active",
        },
        {
            "id": "not_debarred",
            "type": "mandatory",
            "source": "verification_results.debarment.status==clear",
        },
        {
            "id": "pan_valid",
            "type": "mandatory",
            "source": "verification_results.pan.status==valid",
        },
        {
            "id": "document_completeness",
            "type": "mandatory",
            "source": "completeness_check",
        },
    ]

    threshold = mii_local_content_threshold_pct or Decimal(0)
    if threshold > 0:
        criteria.append(
            {
                "id": "local_content_pct",
                "type": "graded",
                "weight": 0.25,
                "threshold": float(threshold),
                "source": "verification_results.mii_local_content.verified_pct_estimate",
            }
        )

    if epfo_applicable_employee_threshold is not None:
        criteria.append(
            {
                "id": "epfo_compliance",
                "type": "graded",
                "weight": 0.10,
                "source": "cross_check.epfo_esic",
            }
        )

    criteria.append(
        {
            "id": "declaration_document_consistency",
            "type": "graded",
            "weight": 0.25,
            "source": "cross_check.declarations",
        }
    )

    if msme_reserved:
        # A reservation is a bar, not a preference: a non-MSME bid is ineligible outright, so
        # this is mandatory rather than a weighted input to the score.
        criteria.append(
            {
                "id": "msme_eligibility",
                "type": "mandatory",
                "source": "verification_results.udyam.category",
            }
        )

    return {"criteria": criteria}


def build_eligibility_rules(tender: dict[str, str]) -> dict[str, Any]:
    """Thin CSV-string adapter over build_eligibility_rules_typed, used by the seeder."""
    return build_eligibility_rules_typed(
        msme_reserved=as_bool(tender["msme_reserved"]),
        mii_local_content_threshold_pct=as_decimal(
            tender["mii_local_content_threshold_pct"]
        ),
        epfo_applicable_employee_threshold=as_int(
            tender["epfo_applicable_employee_threshold"]
        ),
    )


def derive_verification_rows(
    bidder_entry: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any], float | None]]:
    """(source, status, raw, confidence) for each adapter key that isn't not_applicable."""
    rows = []
    for source in ADAPTER_SOURCES:
        payload = bidder_entry.get(source)
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        if status == "not_applicable":
            continue
        if status is None:
            # mii_local_content reports percentages rather than a status verb.
            status = "reported" if "verified_pct_estimate" in payload else "unknown"
        rows.append((source, status, payload, payload.get("confidence")))
    return rows


def split_debarment_period(period: str) -> tuple[date | None, date | None]:
    """'2025-06-01 to 2027-05-31' -> (date(2025, 6, 1), date(2027, 5, 31))."""
    start, _, end = period.partition(" to ")
    return (as_date(start), as_date(end))


@dataclass(frozen=True)
class Fixtures:
    tenders: list[dict[str, str]]
    bidders: list[dict[str, str]]
    requirements: list[dict[str, str]]
    submissions: list[dict[str, str]]
    declarations: list[dict[str, str]]
    portal: dict[str, Any]

    @property
    def bid_ids_by_bidder(self) -> dict[str, str]:
        return {
            row["bidder_id"]: f"BID-{row['bidder_id']}-{row['target_tender_id']}"
            for row in self.bidders
        }

    @property
    def document_type_codes(self) -> list[str]:
        return sorted(
            {row["document_type"] for row in self.requirements}
            | {row["document_type"] for row in self.submissions}
            | set(SPEC_EXTRA_DOCUMENT_TYPES)
        )


def load_fixtures(data_dir: Path) -> Fixtures:
    return Fixtures(
        tenders=read_csv(data_dir / "dummy_tenders.csv"),
        bidders=read_csv(data_dir / "dummy_bidders.csv"),
        requirements=read_csv(data_dir / "dummy_tender_document_requirements.csv"),
        submissions=read_csv(data_dir / "dummy_bid_document_submissions.csv"),
        declarations=read_csv(data_dir / "dummy_bid_declarations.csv"),
        portal=json.loads(
            (data_dir / "dummy_mock_portal_responses.json").read_text(encoding="utf-8")
        ),
    )
