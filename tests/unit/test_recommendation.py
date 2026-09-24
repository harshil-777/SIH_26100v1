from app.services.recommendation import ADVISORY_PREFIX, generate_recommendation


def breakdown(criteria=(), failures=()):
    return {"criteria": list(criteria), "mandatory_failure_reasons": list(failures)}


def test_always_labelled_advisory():
    for text in (
        generate_recommendation(100, "Low", breakdown()),
        generate_recommendation(40, "Non-Compliant", breakdown(failures=["GSTN status is 'cancelled'."])),
    ):
        assert text.startswith(ADVISORY_PREFIX)


def test_clean_bid_recommends_qualifying():
    assert "Recommend qualifying" in generate_recommendation(100, "Low", breakdown())


def test_mandatory_failure_recommends_disqualifying_and_reads_as_sentences():
    text = generate_recommendation(40, "Non-Compliant", breakdown(failures=["Missing mandatory document(s): OEM letter"]))
    assert "failed a mandatory criterion. Missing mandatory document(s): OEM letter. Recommend disqualification" in text


def test_weakest_graded_area_uses_a_readable_name_not_the_id():
    weak = {"id": "declaration_document_consistency", "type": "graded", "score": 50.0, "reason": "Mismatch on GST trade name."}
    text = generate_recommendation(76.19, "Medium", breakdown(criteria=[weak]))
    assert "declaration_document_consistency" not in text
    assert "Weakest area: consistency between declarations, documents and portals. Mismatch on GST trade name." in text
