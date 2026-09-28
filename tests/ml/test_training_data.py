"""Invariants the synthetic training data must hold -- a model is only as good as its labels."""
import random
import re

import pytest

from ml.common.entities import gstin_check_char, random_company
from ml.extraction.fields import LABEL_TO_FIELD, LABELS, normalize
from ml.extraction.metrics import bio_entities, entity_scores
from ml.extraction.templates import TEMPLATES, generate_document
from ml.recommendation.findings import KEYWORDS, verdict
from ml.recommendation.metrics import grade
from ml.recommendation.targets import write_target
from ml.risk.features import FEATURE_NAMES, featurize
from ml.risk.sampler import sample_bid

_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")


def test_gstin_check_character_matches_a_published_gstin():
    assert gstin_check_char("27AAPFU0939F1Z") == "V"


def test_generated_gstins_embed_the_pan_and_carry_a_valid_check_character():
    rng = random.Random(0)
    for _ in range(200):
        c = random_company(rng)
        assert c.gstin[2:12] == c.pan and c.gstin[-1] == gstin_check_char(c.gstin[:14])


@pytest.mark.parametrize("doc_type", list(TEMPLATES))
def test_spans_are_in_bounds_labelled_and_non_overlapping(doc_type):
    rng = random.Random(1)
    for _ in range(50):
        doc = generate_document(rng, doc_type)
        spans = sorted(doc["spans"])
        for start, end, label in spans:
            assert 0 <= start < end <= len(doc["text"]) and label in LABELS
            assert doc["text"][start:end].strip() == doc["text"][start:end]  # no stray whitespace in a label
        for (_, end_a, _), (start_b, _, _) in zip(spans, spans[1:]):
            assert end_a <= start_b


def test_generation_is_deterministic_for_a_seed():
    assert generate_document(random.Random(5)) == generate_document(random.Random(5))


def test_only_the_bidders_gstin_is_labelled_in_an_oem_letter_never_the_oems():
    rng = random.Random(2)
    for _ in range(100):
        doc = generate_document(rng, "OEM_AUTHORIZATION_LETTER")
        labelled = [(s, e) for s, e, label in doc["spans"] if label == "GSTIN"]
        assert len(labelled) == 1
        if doc["noise"] == 0:  # with OCR noise a GSTIN may no longer match the pattern
            gstins = [m.start() for m in _GSTIN.finditer(doc["text"])]
            assert len(gstins) == 2 and labelled[0][0] == gstins[1]  # the OEM's comes first


def test_a_restated_threshold_is_never_labelled_as_local_content():
    rng = random.Random(3)
    checked = 0
    for _ in range(200):
        doc = generate_document(rng, "MII_LOCAL_CONTENT_SELF_CERTIFICATE")
        if doc["noise"]:  # OCR noise can merge lines, so only clean documents have reliable lines
            continue
        text = doc["text"]
        for start, end, label in doc["spans"]:
            if label == "LOCAL_CONTENT":
                line = text[text.rfind("\n", 0, start) + 1 : text.find("\n", end)]
                assert "minimum" not in line.lower(), line
                checked += 1
    assert checked > 20


@pytest.mark.parametrize(("field", "text", "expected"), [
    ("valid_until", "18-Jul-2025", "2025-07-18"),
    ("valid_until", "18/07/2025", "2025-07-18"),
    ("valid_until", "July 18, 2025", "2025-07-18"),
    ("local_content_pct", "40.5 %", 40.5),
    ("enterprise_category", "SMALL", "Small"),
    ("enterprise_category", "Tiny", None),
    ("gstin", " 27aabcn1234a1z5 ", "27AABCN1234A1Z5"),
])
def test_normalize_matches_the_regex_parsers_value_shapes(field, text, expected):
    assert normalize(field, text) == expected


def test_every_label_maps_to_a_field_the_rule_engine_knows():
    assert set(LABEL_TO_FIELD.values()) >= {"gstin", "pan", "udyam_number", "trade_name", "legal_name",
                                            "enterprise_category", "local_content_pct", "valid_until"}


def test_bio_decoding_and_entity_scores():
    tags = ["B-GSTIN", "I-GSTIN", "O", "I-PAN", "B-PAN", "O"]
    assert bio_entities(tags) == {("GSTIN", 0, 2), ("PAN", 3, 4), ("PAN", 4, 5)}
    scores = entity_scores([["B-GSTIN", "I-GSTIN", "O"]], [["B-GSTIN", "O", "O"]])
    assert scores["micro"]["f1"] == 0.0  # a partial span is a miss


def test_featurize_produces_one_value_per_feature_name():
    rng = random.Random(4)
    for _ in range(50):
        bid = sample_bid(rng)
        assert len(featurize(bid["tender"], bid["observed"])) == len(FEATURE_NAMES)


def test_observation_noise_never_adds_facts_the_truth_lacks():
    rng = random.Random(6)
    for _ in range(100):
        bid = sample_bid(rng)
        truth, seen = bid["truth"], bid["observed"]
        assert set(seen["portal"]) <= set(truth["portal"])
        assert set(seen["declarations"]) <= set(truth["declarations"])
        assert seen["missing_docs"] == truth["missing_docs"]


def test_reference_recommendations_mention_every_finding_and_invent_none():
    pytest.importorskip("sqlalchemy")
    from ml.recommendation.findings import finding_key, findings_from_breakdown
    from ml.risk.labeling import score_bid

    rng = random.Random(7)
    for _ in range(300):
        bid = sample_bid(rng)
        score, risk, breakdown = score_bid(bid["tender"], bid["observed"])
        findings = findings_from_breakdown(breakdown)
        keys = sorted({finding_key(f) for f in findings})
        g = grade(write_target(rng, score, risk, findings), verdict(risk, findings), keys)
        assert g["verdict_correct"] and g["findings_mentioned"] == len(keys) and not g["invented"], g


def test_no_keyword_phrase_contains_another_so_a_mention_is_unambiguous():
    phrases = set(KEYWORDS.values())
    for a in phrases:
        for b in phrases - {a}:
            assert a not in b, (a, b)


def test_bids_passing_every_mandatory_check_are_never_labelled_non_compliant():
    pytest.importorskip("sqlalchemy")
    from ml.risk.labeling import score_bid

    rng = random.Random(8)
    checked = 0
    for _ in range(300):
        bid = sample_bid(rng)
        truth, tender = bid["truth"], bid["tender"]
        passes_mandatory = (
            truth["portal"]["gstn"]["status"] == "active"
            and truth["portal"]["pan"]["status"] == "valid"
            and truth["portal"]["debarment"]["status"] == "clear"
            and not truth["missing_docs"]
            and not tender["msme_reserved"]
        )
        if passes_mandatory:
            assert score_bid(tender, truth)[1] != "Non-Compliant"
            checked += 1
    assert checked > 30


def _recommender_with_output(text: str):
    pytest.importorskip("transformers")
    from ml.recommendation.infer import Recommender

    recommender = object.__new__(Recommender)  # no model load: the generated text is stubbed
    recommender._model_text = lambda *args: text
    return recommender


def _non_compliant_breakdown():
    pytest.importorskip("sqlalchemy")
    from ml.risk.labeling import score_bid

    rng = random.Random(9)
    while True:
        bid = sample_bid(rng)
        score, risk, breakdown = score_bid(bid["tender"], bid["observed"])
        if risk == "Non-Compliant":
            return score, risk, breakdown


def test_guardrail_replaces_a_model_output_with_the_wrong_verdict():
    score, risk, breakdown = _non_compliant_breakdown()
    wrong = "AI-generated, advisory only: Everything looks fine. Recommend qualifying, subject to officer review."
    out = _recommender_with_output(wrong).generate_with_check(score, risk, breakdown)
    assert out["source"] == "template_fallback" and "wrong verdict" in out["problems"]
    assert "Recommend disqualification" in out["text"]


def test_guardrail_keeps_a_model_output_that_passes_every_check():
    from ml.recommendation.findings import findings_from_breakdown
    from ml.recommendation.targets import write_target

    score, risk, breakdown = _non_compliant_breakdown()
    good = write_target(random.Random(1), score, risk, findings_from_breakdown(breakdown))
    out = _recommender_with_output(good).generate_with_check(score, risk, breakdown)
    assert out == {"text": good, "source": "model", "problems": []}
