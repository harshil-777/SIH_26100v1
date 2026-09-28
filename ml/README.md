# ML models

Three models, all trained on synthetic data from this directory's generators, all runnable
without any external AI API, all publishable to Hugging Face. They **assist** the platform's
rule engine — which stays the auditable decision of record — rather than replace it.

| Model | Problem-statement items | What it does | Base |
|---|---|---|---|
| `extraction` | 8, 11 | Reads certificate text and extracts GSTIN, PAN, Udyam no., CIN, EPFO code, DPIIT no., names, activity, category, local content %, validity date | `distilbert-base-cased`, token classification |
| `risk` | 11, 12 | Estimates the risk level complete information would give, from what the pipeline observed; flags when missing/misread data is behind a failing verdict; explains each estimate | LightGBM |
| `recommendation` | 13 | Writes the officer recommendation from the score breakdown | `google/flan-t5-small`, seq2seq |

Items 1–10 of the problem statement (portal checks) are lookups against authoritative records, so
they stay as the adapters and rule engine: no model can know whether a GSTIN is cancelled.

## Results so far

| Model | Trained on | Held-out result |
|---|---|---|
| `risk` | **full** 180,000 bids (CPU, ~2 min) | 96.5% accuracy, macro-F1 0.94 — vs. 86.2% / 0.82 for the rule engine on the same noisy observations |
| `extraction` | smoke test only: 1,080 documents, 2 epochs, CPU | 92.5% of fields exactly right vs. 57.0% for today's regex parser (GSTIN 100% vs 77%, validity date 100% vs 75%) |
| `recommendation` | smoke test only: 400 pairs, 3 epochs, CPU | verdict 100%, findings mentioned 87% (12 graded outputs) |

The two transformer models still need their full GPU runs (see below); the smoke tests only prove
the pipelines work end to end.

**How the risk model and the rules divide the work:** the rule engine never misses a truly
non-compliant bid (recall 100%), but 23% of its Non-Compliant verdicts are bidders who would pass
with complete data — a portal timed out, a scan was unreadable. The model gets those right
(precision 99.8%) but misses 2.4% of truly non-compliant bids. So the rules stay the decision of
record, and the model's disagreement tells the officer which failures to re-verify.

**Recommendation guardrail:** every generated recommendation is checked against the input's own
findings — right verdict, every finding mentioned, none invented. If it fails, the deterministic
template text for those findings is returned instead (`Recommender.generate_with_check` reports
which was used), so a model mistake can never reach the officer as advice.

## Quick start

GPU recommended for the two transformer models (free Colab/Kaggle is enough); `risk` trains on CPU
in minutes. The easy path is [`train_on_colab.ipynb`](train_on_colab.ipynb). By hand:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # skip on Colab/Kaggle
pip install -r ml/requirements-ml.txt

python -m ml.extraction.generate --n 60000        # ~1 min
python -m ml.extraction.train                      # ~20 min on a T4
python -m ml.extraction.evaluate                   # model vs. today's regex parser

python -m ml.risk.generate --n 200000              # ~4 min
python -m ml.risk.train                            # ~2 min, CPU

python -m ml.recommendation.generate --n 60000     # ~1 min
python -m ml.recommendation.train                  # ~30 min on a T4
```

Every generator is seeded, so the same command always produces the same data. Outputs go to
`ml/data/` and `ml/models/` (both gitignored: publish to Hugging Face, don't commit).

CPU smoke tests (a few minutes each), to check the pipeline before a full GPU run:

```bash
python -m ml.extraction.generate --n 1200 --out ml/data/extraction_smoke
python -m ml.extraction.train --data ml/data/extraction_smoke --out ml/models/extraction_smoke --epochs 2 --max-length 384 --batch-size 8
python -m ml.recommendation.generate --n 3000 --out ml/data/recommendation_smoke
python -m ml.recommendation.train --data ml/data/recommendation_smoke --out ml/models/recommendation_smoke --limit 1500 --epochs 2 --eval-examples 40
```

## Publishing to Hugging Face

```bash
hf auth login     # once, with a write token from https://huggingface.co/settings/tokens
python -m ml.push_to_hub --model extraction     --repo YOUR_USER/gem-certificate-extractor
python -m ml.push_to_hub --model risk           --repo YOUR_USER/gem-bid-risk --with-dataset
python -m ml.push_to_hub --model recommendation --repo YOUR_USER/gem-recommendation-writer
```

Each upload writes a model card (from `model_cards/`) filled in with that model's own test
metrics. `--with-dataset` also publishes the generated data; add `--private` for private repos.

## How the data is made

- **`common/entities.py`** — synthetic companies with correctly formatted identifiers (GSTINs carry
  a valid check character; PAN's 4th letter encodes the holder type) that match no real entity.
- **`extraction/templates.py`** — nine certificate types, each with varied labels, layouts and date
  formats, OCR-style noise, and the look-alikes regexes get wrong (see the module docstring).
- **`risk/sampler.py`** — a bidder's *true* facts, with independently drawn problems (cancelled GST,
  debarment, inflated declarations, altered certificates, missing documents...), and what the
  pipeline would *observe* of them (portal outages, unreadable scans, fields OCR missed).
- **Labels for `risk` and `recommendation`** come from the app's real rule engine
  (`risk/labeling.py`), so they always agree with production scoring logic.

All three models are only as good as the synthetic data's resemblance to real bids. Before relying
on one, evaluate it on real (anonymised) certificates and bid outcomes.
