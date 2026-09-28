"""Generate the synthetic bid dataset for the risk model.

    python -m ml.risk.generate --n 200000

Each row: {"tender", "observed", "label", "truth_score", "rules_on_observed", "observed_score"}.
  label             -- the rule engine's risk level on the bidder's TRUE facts
  rules_on_observed -- the rule engine's verdict on what the pipeline actually observed
Features come only from "observed", so the model learns what complete information would most
likely conclude; "rules_on_observed" is kept to measure where incomplete data misleads the rules.
"""
import argparse
import random
from collections import Counter
from pathlib import Path

from ml.common.io import DATA_DIR, split_sizes, write_jsonl
from ml.risk.labeling import score_bid
from ml.risk.sampler import sample_bid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--out", default=str(DATA_DIR / "risk"))
    args = parser.parse_args()

    out = Path(args.out)
    labels, disagreements = Counter(), 0
    for split_index, (split, size) in enumerate(split_sizes(args.n).items()):
        rng = random.Random(args.seed * 1000 + split_index)

        def rows():
            nonlocal disagreements
            for i in range(size):
                bid = sample_bid(rng)
                truth_score, label, _ = score_bid(bid["tender"], bid["truth"])
                observed_score, observed_label, _ = score_bid(bid["tender"], bid["observed"])
                labels[label] += 1
                disagreements += label != observed_label
                yield {
                    "id": f"{split}-{i}",
                    "tender": bid["tender"],
                    "observed": bid["observed"],
                    "label": label,
                    "truth_score": truth_score,
                    "rules_on_observed": observed_label,
                    "observed_score": observed_score,
                }

        written = write_jsonl(out / f"{split}.jsonl", rows())
        print(f"{split:<11} {written:>7} bids -> {out / f'{split}.jsonl'}")

    total = sum(labels.values())
    print("label distribution:", {k: f"{v / total:.1%}" for k, v in sorted(labels.items())})
    print(f"rules on observed data disagree with the truth on {disagreements / total:.1%} of bids")


if __name__ == "__main__":
    main()
