"""The extraction model's label set, and how a predicted span becomes a field value.

Field names and value shapes match app/services/ocr.py's parse_fields exactly, so the model's
output can replace the regex output without touching stage 4.
"""
import re
from datetime import date

# Model entity label -> field name in documents.ocr_extracted_json["fields"]
LABEL_TO_FIELD = {
    "GSTIN": "gstin",
    "PAN": "pan",
    "UDYAM": "udyam_number",
    "CIN": "cin",
    "EPFO": "establishment_code",
    "DPIIT": "dpiit_number",
    "TRADE_NAME": "trade_name",
    "LEGAL_NAME": "legal_name",
    "ACTIVITY": "activity",
    "CATEGORY": "enterprise_category",
    "LOCAL_CONTENT": "local_content_pct",
    "VALID_UNTIL": "valid_until",
}
LABELS = list(LABEL_TO_FIELD)
BIO_TAGS = ["O"] + [f"{prefix}-{label}" for label in LABELS for prefix in ("B", "I")]

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
)}
_DATE_PATTERNS = (
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), "ymd"),
    (re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"), "dmy"),
    (re.compile(r"(\d{1,2})[ -]([A-Za-z]{3,9})[ ,-]+(\d{4})"), "d_mon_y"),
    (re.compile(r"([A-Za-z]{3,9}) (\d{1,2}),? (\d{4})"), "mon_d_y"),
)


def parse_date(text: str) -> date | None:
    for pattern, order in _DATE_PATTERNS:
        if not (match := pattern.search(text)):
            continue
        a, b, c = match.groups()
        try:
            if order == "ymd":
                return date(int(a), int(b), int(c))
            if order == "dmy":
                return date(int(c), int(b), int(a))
            if order == "d_mon_y":
                month = _MONTHS.get(b[:3].lower())
                return date(int(c), month, int(a)) if month else None
            month = _MONTHS.get(a[:3].lower())
            return date(int(c), month, int(b)) if month else None
        except ValueError:
            continue
    return None


def normalize(field: str, text: str):
    """A predicted span's text -> the value parse_fields would have produced, or None."""
    text = text.strip(" \t\n:;,.-")
    if not text:
        return None
    if field in ("gstin", "pan", "udyam_number", "cin", "establishment_code", "dpiit_number"):
        return re.sub(r"\s", "", text).upper()
    if field == "local_content_pct":
        match = re.search(r"\d{1,3}(?:\.\d{1,2})?", text)
        return float(match.group(0)) if match else None
    if field == "valid_until":
        parsed = parse_date(text)
        return parsed.isoformat() if parsed else None
    if field == "enterprise_category":
        word = text.split()[0].title()
        return word if word in ("Micro", "Small", "Medium", "Large") else None
    return re.sub(r"\s+", " ", text)
