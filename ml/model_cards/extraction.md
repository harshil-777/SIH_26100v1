---
license: apache-2.0
language: en
library_name: transformers
pipeline_tag: token-classification
base_model: distilbert-base-cased
tags: [token-classification, document-understanding, procurement, india, gem, synthetic-data]
---

# GeM certificate field extractor

Token-classification model that reads the OCR text of Indian business certificates submitted with
Government e-Marketplace (GeM) bids and extracts the fields a compliance officer cross-checks:
GSTIN, PAN, Udyam number, CIN, EPFO establishment code, DPIIT number, legal and trade name,
activity, enterprise category, certified local-content % and validity-until date.

Part of an automated bid-compliance platform; it replaces a regex parser in the document stage,
and its output is cross-verified against government portal data by an auditable rule engine.

## Intended use

Input: plain text from a certificate (PDF text layer or OCR). Output: one value per field, with a
confidence. Covered document types: GST registration certificate (REG-06), Udyam certificate,
Make in India local-content self-certificate, PAN card, EPFO compliance certificate, DPIIT startup
recognition, OEM authorization letter, CA turnover certificate, NSIC registration.

It is an extraction aid, not a verifier: a correctly extracted GSTIN says nothing about whether
that GSTIN is active — that comes from the GST portal.

## Training data

{dataset_note}

The generator deliberately includes look-alikes a regex gets wrong: the OEM's own GSTIN beside the
bidder's in authorization letters, a "minimum local content of N%" threshold restated before the
certified figure, validity *start* dates, PANs embedded in GSTINs, past-year Udyam classifications,
and UDIN/FRN/ESIC numbers — plus OCR-style character confusions (O/0, S/5, I/1) and merged lines.

**All training data is synthetic.** Identifiers follow real formats (GSTINs carry a valid check
character) but correspond to no real entity. Accuracy on real, scanned certificates with layouts
unlike the templates will be lower than the figures below; evaluate on your own documents first.

## Evaluation (held-out synthetic test set)

{metrics_table}

## Usage

```python
from transformers import pipeline
extract = pipeline("token-classification", model="{repo_id}", aggregation_strategy="simple")
extract("Registration Number: 27AABCN1234A1Z5\nLegal Name of Business: Nova Electro Systems Private Limited")
```

For field values normalised exactly as the platform uses them (dates as ISO, local content as a
number, one value per field), use `ml/extraction/infer.py` from the project repository.
