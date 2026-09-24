"""Phase 2's DoD on a real DB: an uploaded certificate is OCR'd during /verify's pipeline and its
fields replace the seed placeholder in cross-verification."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.orchestrator import run_pipeline_standalone
from scripts.make_sample_documents import GST_B009, text_pdf

BID = "BID-B009-T2026-0006"


@pytest.fixture(scope="module")
def client(seeded_db):
    return TestClient(app)


def upload(client, trade_name):
    pdf = text_pdf(GST_B009 + [f"Trade Name, if any: {trade_name}"])
    return client.post(
        f"/bids/{BID}/documents",
        data={"document_type": "GST_CERTIFICATE"},
        files={"file": ("gst.pdf", pdf, "application/pdf")},
    )


def gst_comparisons(client):
    criteria = client.get(f"/bids/{BID}/compliance-score").json()["criterion_breakdown_json"]["criteria"]
    return next(c for c in criteria if c["id"] == "declaration_document_consistency")["evidence"]


async def test_mismatching_certificate_is_detected_from_the_document_itself(client):
    response = upload(client, "Om Security & Facility Services")
    assert response.status_code == 201, response.text
    # No Redis in tests: the upload still succeeds and OCR is deferred to the pipeline.
    assert response.json()["ocr_status"] == "pending_verification"

    await run_pipeline_standalone(BID)
    evidence = gst_comparisons(client)
    trade = evidence["comparisons"]["gst_trade_name"]
    assert trade["match"] is False
    assert trade["document"] == "Om Security & Facility Services"
    assert evidence["superseded_placeholders"] == ["gst_certificate"]

    documents = client.get(f"/bids/{BID}/documents").json()
    gst = next(d for d in documents if d["document_type"] == "GST_CERTIFICATE")
    assert gst["is_placeholder"] is False and gst["ocr"]["status"] == "extracted"


async def test_matching_certificate_clears_the_flag(client):
    assert upload(client, "Om Security Services").status_code == 201
    summary = await run_pipeline_standalone(BID)
    assert gst_comparisons(client)["comparisons"]["gst_trade_name"]["match"] is True
    assert summary["risk_level"] == "Low"


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"document_type": "GST_CERTIFICATE", "file": ("x.txt", b"hello", "text/plain")}, 415),
        ({"document_type": "NOT_A_TYPE", "file": ("x.pdf", b"%PDF-1.4", "application/pdf")}, 422),
        ({"document_type": "GST_CERTIFICATE", "file": ("x.pdf", b"", "application/pdf")}, 400),
    ],
)
def test_upload_validation(client, payload, status):
    file = payload.pop("file")
    assert client.post(f"/bids/{BID}/documents", data=payload, files={"file": file}).status_code == status


def test_upload_to_unknown_bid_is_404(client):
    response = client.post("/bids/BID-NOPE/documents", data={"document_type": "GST_CERTIFICATE"}, files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 404
