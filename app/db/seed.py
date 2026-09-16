"""Load the six fixture files into Postgres (BUILD_SPEC.md section 4).

Run with: python -m app.db.seed
"""
import asyncio
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.fixtures import (
    DOCUMENT_TYPE_DISPLAY_NAMES,
    EXTRA_DEBARRED_ENTITIES,
    as_bool,
    as_date,
    as_decimal,
    as_int,
    as_text,
    as_utc_datetime,
    build_eligibility_rules,
    derive_verification_rows,
    load_fixtures,
    split_debarment_period,
)
from app.db.session import SessionLocal
from app.models import (
    AuditLog,
    Bid,
    Bidder,
    BidDeclaration,
    BidDocumentSubmission,
    ComplianceScore,
    DebarredEntity,
    Document,
    DocumentType,
    Tender,
    TenderDocumentRequirement,
    VerificationResult,
)

# Wipe order is the reverse of the insert order; foreign keys require it.
TRUNCATE_ORDER = (
    AuditLog,
    ComplianceScore,
    VerificationResult,
    Document,
    DebarredEntity,
    BidDeclaration,
    BidDocumentSubmission,
    TenderDocumentRequirement,
    Bid,
    DocumentType,
    Bidder,
    Tender,
)


async def seed(session: AsyncSession, data_dir: Path) -> dict[str, int]:
    fx = load_fixtures(data_dir)

    for model in TRUNCATE_ORDER:
        await session.execute(delete(model))

    # 1. tenders
    session.add_all(
        Tender(
            tender_id=row["tender_id"],
            title=row["title"],
            department=row["department"],
            category=row["category"],
            estimated_value_inr=as_decimal(row["estimated_value_inr"]),
            msme_reserved=as_bool(row["msme_reserved"]),
            mii_local_content_threshold_pct=as_decimal(
                row["mii_local_content_threshold_pct"]
            ),
            requires_oem_authorization=as_bool(row["requires_oem_authorization"]),
            epfo_applicable_employee_threshold=as_int(
                row["epfo_applicable_employee_threshold"]
            ),
            submission_deadline=as_date(row["submission_deadline"]),
            eligibility_rules_json=build_eligibility_rules(row),
        )
        for row in fx.tenders
    )

    # 2. bidders -- target_tender_id / scenario_tag / expected_ground_truth are test-fixture
    # metadata driving step 3 only; declared_local_content_pct has no column in the schema.
    session.add_all(
        Bidder(
            bidder_id=row["bidder_id"],
            name=row["name"],
            pan=row["pan"],
            gstin=as_text(row["gstin"]),
            udyam_number=as_text(row["udyam_number"]),
            cin=as_text(row["cin"]),
            dpiit_recognition_number=as_text(row["dpiit_recognition_number"]),
            nsic_registration_number=as_text(row["nsic_registration_number"]),
            epfo_establishment_code=as_text(row["epfo_establishment_code"]),
            employee_count=as_int(row["employee_count"]),
            enterprise_category=as_text(row["enterprise_category"]),
            state=as_text(row["state"]),
        )
        for row in fx.bidders
    )
    await session.flush()

    # 3. bids -- one per bidder; the ID shape must reproduce the IDs the submission and
    # declaration fixtures already reference.
    bid_ids = fx.bid_ids_by_bidder
    session.add_all(
        Bid(
            bid_id=bid_ids[row["bidder_id"]],
            tender_id=row["target_tender_id"],
            bidder_id=row["bidder_id"],
        )
        for row in fx.bidders
    )

    # 4. document_types -- derived from the two fixtures, not hand-maintained
    type_codes = fx.document_type_codes
    session.add_all(
        DocumentType(
            type_code=code,
            display_name=DOCUMENT_TYPE_DISPLAY_NAMES.get(
                code, code.replace("_", " ").title()
            ),
        )
        for code in type_codes
    )
    await session.flush()

    # 5. tender_document_requirements
    session.add_all(
        TenderDocumentRequirement(
            requirement_id=row["requirement_id"],
            tender_id=row["tender_id"],
            document_type=row["document_type"],
            buyer_label=as_text(row["buyer_label"]),
            requirement_source=row["requirement_source"],
            mandatory=as_bool(row["mandatory"]),
            notes=as_text(row["notes"]),
        )
        for row in fx.requirements
    )

    # 6. bid_document_submissions
    session.add_all(
        BidDocumentSubmission(
            submission_id=row["submission_id"],
            bid_id=row["bid_id"],
            bidder_id=row["bidder_id"],
            tender_id=row["tender_id"],
            document_type=row["document_type"],
            submitted=as_bool(row["submitted"]),
            file_ref=as_text(row["file_ref"]),
            note=as_text(row["note"]),
        )
        for row in fx.submissions
    )

    # 7. bid_declarations
    session.add_all(
        BidDeclaration(
            declaration_id=row["declaration_id"],
            bid_id=row["bid_id"],
            bidder_id=row["bidder_id"],
            tender_id=row["tender_id"],
            criterion_code=row["criterion_code"],
            declared_value=row["declared_value"],
            declared_at=as_utc_datetime(row["declared_at"]),
            note=as_text(row["note"]),
        )
        for row in fx.declarations
    )
    await session.flush()

    # 8. verification_results -- one row per bid per non-not_applicable adapter key. The
    # mock adapter registry reads the same JSON at runtime; seeding it here just means the
    # dashboard has something to show before the pipeline has ever run.
    verification_count = 0
    for entry in fx.portal["bidders"]:
        bid_id = bid_ids.get(entry["bidder_id"])
        if bid_id is None:
            continue
        for source, status, raw, confidence in derive_verification_rows(entry):
            session.add(
                VerificationResult(
                    bid_id=bid_id,
                    source=source,
                    status=status,
                    raw_response_json=raw,
                    confidence_score=(
                        Decimal(str(confidence)) if confidence is not None else None
                    ),
                )
            )
            verification_count += 1

    # 9. debarred_entities
    bidders_by_id = {row["bidder_id"]: row for row in fx.bidders}
    debarred_rows: list[DebarredEntity] = []
    for entry in fx.portal["bidders"]:
        debarment = entry.get("debarment", {})
        if debarment.get("status") != "debarred":
            continue
        bidder = bidders_by_id[entry["bidder_id"]]
        debarred_from, debarred_until = split_debarment_period(
            debarment.get("debarment_period", "")
        )
        debarred_rows.append(
            DebarredEntity(
                pan=bidder["pan"],
                gstin=as_text(bidder["gstin"]),
                name=bidder["name"],
                order_reference=debarment.get("order_reference"),
                debarred_from=debarred_from,
                debarred_until=debarred_until,
                list_source=debarment.get("list_source"),
            )
        )
    debarred_rows.extend(DebarredEntity(**row) for row in EXTRA_DEBARRED_ENTITIES)
    session.add_all(debarred_rows)

    # 10. documents -- placeholder rows for submitted files. These file_refs are not real
    # files; Phase 2 replaces them with real uploads and real OCR output.
    document_rows = [
        Document(
            bid_id=row["bid_id"],
            doc_type=row["document_type"],
            file_url=as_text(row["file_ref"]),
        )
        for row in fx.submissions
        if as_bool(row["submitted"]) and as_text(row["file_ref"])
    ]
    session.add_all(document_rows)

    await session.commit()

    return {
        "tenders": len(fx.tenders),
        "bidders": len(fx.bidders),
        "bids": len(bid_ids),
        "document_types": len(type_codes),
        "tender_document_requirements": len(fx.requirements),
        "bid_document_submissions": len(fx.submissions),
        "bid_declarations": len(fx.declarations),
        "verification_results": verification_count,
        "debarred_entities": len(debarred_rows),
        "documents": len(document_rows),
    }


async def main() -> None:
    async with SessionLocal() as session:
        counts = await seed(session, get_settings().seed_data_dir)
    for table, count in counts.items():
        print(f"{table:<32} {count:>4}")


if __name__ == "__main__":
    asyncio.run(main())
