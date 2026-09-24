"""Generate sample certificates for exercising the upload + OCR path.

Run from the repo root: python scripts/make_sample_documents.py
Writes to samples/ (gitignored). Each file matches a seeded bid's scenario, so uploading it
through POST /bids/{bid_id}/documents and re-running /verify shows real OCR output replacing
the fixture's placeholder cross-check.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("samples")


def text_pdf(lines: list[str]) -> bytes:
    """A minimal single-page PDF with a real text layer (no OCR needed to read it)."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream = "BT /F1 12 Tf 50 790 Td 18 TL " + " ".join(f"({line}) Tj T*" for line in escaped) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def text_image(lines: list[str]) -> Image.Image:
    """The same content rendered as a picture -- only readable via OCR."""
    font = ImageFont.load_default(size=30)
    image = Image.new("RGB", (1700, 120 + 55 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((60, 60 + 55 * i), line, fill="black", font=font)
    return image


GST_B009 = [
    "Government of India - Form GST REG-06",
    "Registration Certificate",
    "Registration Number: 33HOSSP7890R1Z1",
    "Legal Name of Business: Om Security Services",
]
MII_B006 = [
    "MAKE IN INDIA - SELF CERTIFICATION (CLASS-I LOCAL SUPPLIER)",
    "Bidder: SolarTech Renewables Pvt Ltd, GSTIN 08ESTRP4567O1Z0",
    "We certify that the item offered meets the minimum local content of 60% as required.",
    "The local content of the offered item is 40%.",
]
UDYAM_B001 = [
    "UDYAM REGISTRATION CERTIFICATE",
    "UDYAM REGISTRATION NUMBER: UDYAM-MH-03-0012345",
    "Name of Enterprise: Nova Electro Systems Private Limited",
    "Type of Enterprise: Small",
    "Major Activity: Manufacturing - Electronics",
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    files = {
        # Matches the live GSTN record -> supersedes the fixture's "name mismatch" placeholder.
        "B009_gst_certificate_matching.pdf": text_pdf(GST_B009 + ["Trade Name, if any: Om Security Services"]),
        # The seeded scenario for real: trade name differs from the GSTN record.
        "B009_gst_certificate_mismatch.pdf": text_pdf(
            GST_B009 + ["Trade Name, if any: Om Security & Facility Services"]
        ),
        "B001_udyam_certificate.pdf": text_pdf(UDYAM_B001),
        "corrupt.pdf": b"%PDF-1.4\nthis is not really a pdf\n",
    }
    for name, data in files.items():
        (OUT / name).write_bytes(data)

    mii = text_image(MII_B006)
    mii.save(OUT / "B006_mii_certificate.png")
    # Image-only PDF: no text layer, so it exercises the scanned-PDF OCR path.
    mii.save(OUT / "B006_mii_certificate_scanned.pdf", "PDF", resolution=150)

    for path in sorted(OUT.iterdir()):
        print(f"{path}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
