"""Rule engine: mandatory checks, the MSME reservation, exemption proofs, cross-verification."""
from app.db.fixtures import build_eligibility_rules_typed
from app.services.rule_engine import evaluate_criteria
from tests.unit.factories import make_facts


def outcome(facts, criterion):
    return evaluate_criteria({"criteria": [criterion]}, facts)[0]


# --- statutory mandatory checks -------------------------------------------------------------

def test_cancelled_gstin_fails_gst_active_with_the_portal_status_as_reason():
    result = outcome(make_facts(portals={"gstn": {"status": "cancelled"}}), {"id": "gst_active", "type": "mandatory"})
    assert result.passed is False
    assert "cancelled" in result.reason


def test_debarred_bidder_fails_not_debarred():
    assert outcome(make_facts(portals={"debarment": {"status": "debarred"}}), {"id": "not_debarred", "type": "mandatory"}).passed is False


# --- MSME reservation ------------------------------------------------------------------------

def test_reserved_tender_config_makes_msme_eligibility_mandatory():
    rules = build_eligibility_rules_typed(msme_reserved=True, mii_local_content_threshold_pct=None, epfo_applicable_employee_threshold=None)
    msme = next(c for c in rules["criteria"] if c["id"] == "msme_eligibility")
    assert msme["type"] == "mandatory" and "weight" not in msme


def test_unreserved_tender_config_has_no_msme_criterion():
    rules = build_eligibility_rules_typed(msme_reserved=False, mii_local_content_threshold_pct=None, epfo_applicable_employee_threshold=None)
    assert all(c["id"] != "msme_eligibility" for c in rules["criteria"])


def test_large_enterprise_fails_mandatory_msme_eligibility_as_an_eligibility_bar():
    facts = make_facts(portals={"udyam": {"status": "not_found"}})
    result = outcome(facts, {"id": "msme_eligibility", "type": "mandatory"})
    assert result.passed is False
    assert "eligibility bar" in result.reason


def test_medium_enterprise_is_still_msme_eligible():
    facts = make_facts(portals={"udyam": {"status": "valid", "category": "Medium"}})
    assert outcome(facts, {"id": "msme_eligibility", "type": "mandatory"}).passed is True


def test_category_from_an_invalid_udyam_record_does_not_count():
    facts = make_facts(portals={"udyam": {"status": "cancelled", "category": "Small"}})
    assert outcome(facts, {"id": "msme_eligibility", "type": "mandatory"}).passed is False


def test_legacy_graded_msme_config_is_still_scored_as_graded():
    facts = make_facts(portals={"udyam": {"status": "not_found"}})
    result = outcome(facts, {"id": "msme_eligibility", "type": "graded", "weight": 0.2})
    assert (result.type, result.score, result.passed) == ("graded", 0.0, None)


# --- completeness and exemption proofs -------------------------------------------------------

COMPLETENESS = {"id": "document_completeness", "type": "mandatory"}


def test_missing_mandatory_document_fails_completeness():
    result = outcome(make_facts(missing=["OEM_AUTHORIZATION_LETTER"]), COMPLETENESS)
    assert result.passed is False
    assert [m["document_type"] for m in result.evidence["missing_documents"]] == ["OEM_AUTHORIZATION_LETTER"]


def test_missing_exemption_proof_from_a_non_mse_is_not_applicable_rather_than_a_gap():
    facts = make_facts(portals={"udyam": {"status": "not_found"}}, missing=["EMD_EXEMPTION_PROOF"])
    result = outcome(facts, COMPLETENESS)
    assert result.passed is True
    assert [d["document_type"] for d in result.evidence["not_applicable_documents"]] == ["EMD_EXEMPTION_PROOF"]


def test_missing_exemption_proof_from_an_mse_is_still_a_gap():
    result = outcome(make_facts(missing=["EMD_EXEMPTION_PROOF"]), COMPLETENESS)
    assert result.passed is False


def test_recognized_startup_can_claim_the_exemption_so_its_missing_proof_is_a_gap():
    facts = make_facts(portals={"udyam": {"status": "not_found"}, "startup_india": {"status": "recognized"}}, missing=["EMD_EXEMPTION_PROOF"])
    assert outcome(facts, COMPLETENESS).passed is False


def test_exemption_rule_never_hides_other_missing_documents():
    facts = make_facts(portals={"udyam": {"status": "not_found"}}, missing=["EMD_EXEMPTION_PROOF", "QUALITY_BIS_CERTIFICATE"])
    result = outcome(facts, COMPLETENESS)
    assert result.passed is False
    assert [m["document_type"] for m in result.evidence["missing_documents"]] == ["QUALITY_BIS_CERTIFICATE"]


# --- graded criteria -------------------------------------------------------------------------

def test_local_content_below_threshold_scores_proportionally():
    facts = make_facts(portals={"mii_local_content": {"verified_pct_estimate": 38}})
    result = outcome(facts, {"id": "local_content_pct", "type": "graded", "weight": 0.25, "threshold": 60})
    assert round(result.score, 2) == 63.33
    assert "below the 60% threshold" in result.reason


def test_epfo_employee_count_mismatch_scores_zero():
    facts = make_facts(portals={"epfo_esic": {"status": "active", "registered_employee_count": 8}}, employees=25)
    assert outcome(facts, {"id": "epfo_compliance", "type": "graded", "weight": 0.1}).score == 0.0


# --- three-way cross-verification ------------------------------------------------------------

CONSISTENCY = {"id": "declaration_document_consistency", "type": "graded", "weight": 0.25}


def gst_upload(trade_name):
    return {"GST_CERTIFICATE": {"status": "extracted", "fields": {"gstin": "27AABCN1234A1Z5", "trade_name": trade_name}}}


def test_trade_name_differing_from_gstn_is_a_mismatch_named_readably():
    result = outcome(make_facts(ocr=gst_upload("Nova Electro & Facility Services")), CONSISTENCY)
    comparison = result.evidence["comparisons"]["gst_trade_name"]
    assert comparison["match"] is False and comparison["mismatched_pairs"] == ["document_vs_portal"]
    assert "GST trade name" in result.reason and "gst_trade_name" not in result.reason


def test_names_differing_only_in_legal_suffix_and_case_still_match():
    facts = make_facts(ocr=gst_upload("NOVA ELECTRO SYSTEMS PVT LTD"))
    assert outcome(facts, CONSISTENCY).evidence["comparisons"]["gst_trade_name"]["match"] is True


def test_real_upload_supersedes_the_seed_placeholder_for_that_document():
    facts = make_facts(ocr=gst_upload("Nova Electro Systems"), cross_check=[{"doc_type": "gst_certificate", "match": False, "note": "seeded"}])
    evidence = outcome(facts, CONSISTENCY).evidence
    assert "placeholder:gst_certificate" not in evidence["comparisons"]
    assert evidence["superseded_placeholders"] == ["gst_certificate"]


def test_unreadable_upload_is_reported_but_does_not_lower_the_score():
    facts = make_facts(ocr={"PAN_CARD": {"status": "failed", "error": "not a PDF"}})
    result = outcome(facts, CONSISTENCY)
    assert result.evidence["unreadable_documents"] == {"PAN_CARD": "not a PDF"}
    assert result.score == 100.0
