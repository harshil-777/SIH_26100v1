---
license: apache-2.0
library_name: lightgbm
tags: [tabular-classification, risk-scoring, procurement, india, gem, synthetic-data, explainability]
---

# GeM bid compliance risk estimator

LightGBM classifier that estimates a Government e-Marketplace (GeM) bid's compliance risk level
(Low / Medium / High / Non-Compliant) from what an automated verification pipeline observed:
portal statuses (GSTN, PAN, Udyam, EPFO/ESIC, Startup India, debarment registry, Make in India
local content), document extraction results, bidder self-declarations and missing documents.

## What it is for — and what it is not

It **assists** an auditable rule engine; it never replaces it. The rule engine's verdict on the
evidence it has remains the decision of record. The model estimates what the verdict would be *with
complete, correct information*, so its disagreement with the rules is a signal to the officer:
for example, rules say Non-Compliant because the GST portal timed out, while the model estimates
Low — meaning "re-verify", not "accept". Every prediction comes with the observed facts that drove
it (exact per-prediction SHAP contributions from LightGBM).

Do not use it to disqualify or qualify a bid on its own.

## Training data

{dataset_note}

Labels are produced by the platform's actual rule engine run on each synthetic bidder's *true*
facts; features come only from *noisy observations* of those facts (portal outages, unreadable
scans, fields OCR missed, blank declarations). **All data is synthetic**; the base rates of each
problem are assumptions, not measurements of real GeM bids, so calibrate on real outcomes before
relying on the probabilities.

## Evaluation (held-out synthetic test set)

{metrics_table}

## Usage

Files: `model.txt` (LightGBM text format — no pickle), `features.json` (feature order and
encodings), `features.py` and `infer.py` (the featuriser and predictor).

```python
from huggingface_hub import snapshot_download
path = snapshot_download("{repo_id}")
# with features.py / infer.py importable (see the project repository, ml/risk/):
from ml.risk.infer import RiskModel
RiskModel(path).predict(tender, observed)  # -> risk_level, probabilities, top_factors
```
