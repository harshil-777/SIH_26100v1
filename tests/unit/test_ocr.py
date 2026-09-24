"""Document extraction: file-type sniffing, field parsing, and text/scanned PDF paths."""
import io
import shutil

import pytest

from app.services.ocr import detect_file_kind, extract_document, parse_fields
from scripts.make_sample_documents import GST_B009, MII_B006, UDYAM_B001, text_image, text_pdf

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract binary not installed")


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"%PDF-1.4\n...", "pdf"),
        (b"\x89PNG\r\n\x1a\n...", "png"),
        (b"\xff\xd8\xff\xe0...", "jpeg"),
        (b"II*\x00...", "tiff"),
        (b"hello, I am a text file", None),
        (b"<script>%PDF</script>", None),  # decided by leading bytes only
    ],
)
def test_file_kind_comes_from_leading_bytes(data, kind):
    assert detect_file_kind(data) == kind


def test_gst_certificate_fields():
    fields = parse_fields("\n".join(GST_B009 + ["Trade Name, if any: Om Security & Facility Services"]))
    assert fields["gstin"] == "33HOSSP7890R1Z1"
    assert fields["legal_name"] == "Om Security Services"
    assert fields["trade_name"] == "Om Security & Facility Services"


def test_udyam_certificate_fields():
    fields = parse_fields("\n".join(UDYAM_B001))
    assert fields["udyam_number"] == "UDYAM-MH-03-0012345"
    assert fields["enterprise_category"] == "Small"


def test_restated_minimum_threshold_is_not_read_as_the_certified_local_content():
    assert parse_fields("\n".join(MII_B006))["local_content_pct"] == 40.0


def test_absent_fields_are_omitted_not_guessed():
    assert parse_fields("Certificate of appreciation for outstanding service") == {}


def test_text_layer_pdf_is_read_without_ocr():
    result = extract_document(text_pdf(UDYAM_B001), file_hash="h")
    assert (result["status"], result["method"]) == ("extracted", "pdf_text_layer")
    assert result["fields"]["udyam_number"] == "UDYAM-MH-03-0012345"


def test_corrupt_pdf_fails_cleanly_without_raising():
    result = extract_document(b"%PDF-1.4\nthis is not really a pdf\n", file_hash="h")
    assert result["status"] == "failed" and result["error"]


def test_unsupported_bytes_fail_cleanly():
    assert extract_document(b"plain text", file_hash="h")["status"] == "failed"


@needs_tesseract
def test_png_is_read_with_tesseract():
    buffer = io.BytesIO()
    text_image(MII_B006).save(buffer, "PNG")
    result = extract_document(buffer.getvalue(), file_hash="h")
    assert (result["status"], result["method"]) == ("extracted", "tesseract")
    assert result["fields"]["local_content_pct"] == 40.0


@needs_tesseract
def test_image_only_pdf_falls_back_to_tesseract():
    buffer = io.BytesIO()
    text_image(MII_B006).save(buffer, "PDF", resolution=150)
    result = extract_document(buffer.getvalue(), file_hash="h")
    assert (result["status"], result["method"]) == ("extracted", "pdf_tesseract")
