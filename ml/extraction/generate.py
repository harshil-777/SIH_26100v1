"""Generate the synthetic certificate dataset for the extraction model.

    python -m ml.extraction.generate --n 60000

Writes ml/data/extraction/{train,validation,test}.jsonl; each line is
{"id", "doc_type", "text", "spans": [[start, end, label], ...], "noise"}.
Each split uses its own seed, so regenerating one split never changes another.
"""
import argparse
import random
from collections import Counter
from pathlib import Path

from ml.common.io import DATA_DIR, split_sizes, write_jsonl
from ml.extraction.templates import generate_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60000, help="total documents across all splits")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--out", default=str(DATA_DIR / "extraction"))
    args = parser.parse_args()

    out = Path(args.out)
    label_counts: Counter = Counter()
    for split_index, (split, size) in enumerate(split_sizes(args.n).items()):
        rng = random.Random(args.seed * 1000 + split_index)

        def rows():
            for i in range(size):
                doc = generate_document(rng)
                label_counts.update(label for _, _, label in doc["spans"])
                yield {"id": f"{split}-{i}", **doc}

        written = write_jsonl(out / f"{split}.jsonl", rows())
        print(f"{split:<11} {written:>7} documents -> {out / f'{split}.jsonl'}")

    print("entity counts:", dict(sorted(label_counts.items())))


if __name__ == "__main__":
    main()
