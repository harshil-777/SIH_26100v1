---
license: apache-2.0
language: en
library_name: transformers
pipeline_tag: text2text-generation
base_model: google/flan-t5-small
tags: [text2text-generation, procurement, india, gem, synthetic-data]
---

# GeM bid recommendation writer

Small seq2seq model that turns a bid's structured compliance breakdown (risk level, score and the
findings of an automated verification pipeline) into a short recommendation for a procurement
officer, ending in one of: *Recommend qualifying*, *Recommend disqualification*, or *Recommend
officer review before qualifying*. Every output is labelled "AI-generated, advisory only".

It runs locally — no external LLM API — and only ever sees the structured summary, never raw
bidder documents.

## Intended use

Advisory text for a dashboard. The officer makes the decision; the platform's rule engine and
audit log remain the record. Input format (built by `ml/recommendation/findings.py`):

```
write recommendation | risk: Non-Compliant | score: 40.0 | findings: gst_inactive status=cancelled ; mismatch:gst_trade_name document=... portal=...
```

## Guardrail (use it)

A small generative model can occasionally state the wrong verdict, drop a finding or invent one.
The project's `ml/recommendation/infer.py` checks every output against the input's own findings
and falls back to deterministic template text for the same findings when the check fails. Use it
rather than raw `pipeline(...)` output anywhere an officer will read the result.

## Training data

{dataset_note}

Targets are written by a template generator with varied phrasing and a concrete next step per
finding (e.g. "request recent ECR challans"). **All data is synthetic**, so the model's language is
bounded by those templates: it combines and rephrases them fluently for any mix of findings, but
does not reason beyond them.

## Evaluation (generated outputs on held-out synthetic bids)

Graded on what matters to an officer rather than n-gram overlap: the right verdict, every finding
in the input mentioned, and no finding invented.

{metrics_table}

## Usage

```python
from transformers import pipeline
write = pipeline("text2text-generation", model="{repo_id}")
write("write recommendation | risk: Low | score: 100.0 | findings: none", max_new_tokens=200, num_beams=4)
```
