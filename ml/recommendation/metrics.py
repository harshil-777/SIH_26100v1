"""Grade generated recommendations on what matters to an officer, not n-gram overlap.

  verdict_accuracy   -- ends in the right one of qualify / disqualify / review
  finding_recall     -- every finding in the input is mentioned (its KEYWORDS phrase appears)
  invented_rate      -- share of outputs mentioning a finding type that isn't in the input
Quoted values ('...') are ignored when looking for invented findings: company names can contain
any word ("... Manufacturers") without that being a claim about the bid.
"""
import re

from ml.recommendation.findings import KEYWORDS

VERDICT_PHRASES = {
    "qualify": "recommend qualifying",
    "disqualify": "recommend disqualification",
    "review": "recommend officer review before qualifying",
}


def grade(output: str, verdict: str, finding_keys: list[str]) -> dict:
    text = output.lower()
    unquoted = re.sub(r"'[^']*'", "", text)
    said = {v for v, phrase in VERDICT_PHRASES.items() if phrase in text}
    present = {KEYWORDS[k] for k in finding_keys}
    invented = [k for k, kw in KEYWORDS.items() if k not in finding_keys and kw not in present and kw in unquoted]
    return {
        "verdict_correct": said == {verdict},
        "findings_mentioned": sum(KEYWORDS[k] in text for k in finding_keys),
        "findings_total": len(finding_keys),
        "invented": invented,
        "advisory_label": text.startswith("ai-generated, advisory only"),
    }


def summarize(grades: list[dict]) -> dict:
    n = max(1, len(grades))
    total_findings = sum(g["findings_total"] for g in grades)
    return {
        "examples": len(grades),
        "verdict_accuracy": round(sum(g["verdict_correct"] for g in grades) / n, 4),
        "finding_recall": round(sum(g["findings_mentioned"] for g in grades) / max(1, total_findings), 4),
        "invented_rate": round(sum(bool(g["invented"]) for g in grades) / n, 4),
        "advisory_label_rate": round(sum(g["advisory_label"] for g in grades) / n, 4),
    }
