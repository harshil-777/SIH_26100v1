"""Field-level comparison: trained model vs. the app's current regex parser, on the test split.

    python -m ml.extraction.evaluate --model ml/models/extraction

For each field: accuracy on documents that contain it (exact normalised value), and false
positives on documents that don't. The regex baseline needs the app importable (run from the
repo with requirements.txt installed); it is skipped otherwise.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from ml.common.io import DATA_DIR, MODELS_DIR, read_jsonl
from ml.extraction.fields import LABEL_TO_FIELD, normalize
from ml.extraction.infer import FieldExtractor


def gold_fields(row: dict) -> dict:
    fields = {}
    for start, end, label in row["spans"]:
        field = LABEL_TO_FIELD[label]
        if field not in fields and (value := normalize(field, row["text"][start:end])) is not None:
            fields[field] = value
    return fields


def score(predictions: list[dict], golds: list[dict]) -> dict:
    correct, present, false_pos, absent = Counter(), Counter(), Counter(), Counter()
    for pred, gold in zip(predictions, golds):
        for field in LABEL_TO_FIELD.values():
            if field in gold:
                present[field] += 1
                correct[field] += pred.get(field) == gold[field]
            else:
                absent[field] += 1
                false_pos[field] += field in pred
    per_field = {
        f: {
            "accuracy": round(correct[f] / present[f], 4) if present[f] else None,
            "false_positive_rate": round(false_pos[f] / absent[f], 4) if absent[f] else None,
            "support": present[f],
        }
        for f in LABEL_TO_FIELD.values()
    }
    return {
        "overall_accuracy": round(sum(correct.values()) / max(1, sum(present.values())), 4),
        "overall_false_positive_rate": round(sum(false_pos.values()) / max(1, sum(absent.values())), 4),
        "per_field": per_field,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(MODELS_DIR / "extraction"))
    parser.add_argument("--data", default=str(DATA_DIR / "extraction" / "test.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = list(read_jsonl(Path(args.data)))[: args.limit]
    golds = [gold_fields(r) for r in rows]
    extractor = FieldExtractor(args.model)
    results = {"model": score([extractor.extract(r["text"])["fields"] for r in rows], golds)}

    try:
        from app.services.ocr import parse_fields
    except Exception as exc:  # app deps not installed (e.g. on Colab)
        print(f"regex baseline skipped: {exc}")
    else:
        results["regex_baseline"] = score([parse_fields(r["text"]) for r in rows], golds)

    print(f"{'field':<22}{'model acc':>10}{'regex acc':>11}{'model FP':>10}{'regex FP':>10}")
    for field in LABEL_TO_FIELD.values():
        m = results["model"]["per_field"][field]
        r = results.get("regex_baseline", {}).get("per_field", {}).get(field, {})
        fmt = lambda v: "-" if v is None else f"{v:.3f}"  # noqa: E731
        print(f"{field:<22}{fmt(m['accuracy']):>10}{fmt(r.get('accuracy')):>11}"
              f"{fmt(m['false_positive_rate']):>10}{fmt(r.get('false_positive_rate')):>10}")
    for name, res in results.items():
        print(f"{name}: accuracy {res['overall_accuracy']}, false-positive rate {res['overall_false_positive_rate']}")

    out = Path(args.model) / "field_eval.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"written to {out}")


if __name__ == "__main__":
    main()
