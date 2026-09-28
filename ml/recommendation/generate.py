"""Generate (structured score breakdown -> recommendation text) pairs.

    python -m ml.recommendation.generate --n 60000

Bids come from the same sampler as the risk model and are scored by the app's real rule
engine on what the pipeline observed, so inputs look exactly like production breakdowns.
Each row: {"id", "input", "target", "verdict", "finding_keys"}.
"""
import argparse
import random
from collections import Counter
from pathlib import Path

from ml.common.io import DATA_DIR, split_sizes, write_jsonl
from ml.recommendation.findings import build_input, finding_key, findings_from_breakdown, verdict
from ml.recommendation.targets import write_target
from ml.risk.labeling import score_bid
from ml.risk.sampler import sample_bid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60000)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--out", default=str(DATA_DIR / "recommendation"))
    args = parser.parse_args()

    out = Path(args.out)
    verdicts, n_findings = Counter(), Counter()
    for split_index, (split, size) in enumerate(split_sizes(args.n).items()):
        rng = random.Random(args.seed * 1000 + split_index)

        def rows():
            for i in range(size):
                bid = sample_bid(rng)
                score, risk, breakdown = score_bid(bid["tender"], bid["observed"])
                findings = findings_from_breakdown(breakdown)
                verdicts[verdict(risk, findings)] += 1
                n_findings[min(len(findings), 4)] += 1
                yield {
                    "id": f"{split}-{i}",
                    "input": build_input(score, risk, breakdown),
                    "target": write_target(rng, score, risk, findings),
                    "verdict": verdict(risk, findings),
                    "finding_keys": sorted({finding_key(f) for f in findings}),
                }

        written = write_jsonl(out / f"{split}.jsonl", rows())
        print(f"{split:<11} {written:>7} pairs -> {out / f'{split}.jsonl'}")

    total = sum(verdicts.values())
    print("verdicts:", {k: f"{v / total:.1%}" for k, v in sorted(verdicts.items())})
    print("findings per bid (4 = 4+):", {k: f"{v / total:.1%}" for k, v in sorted(n_findings.items())})


if __name__ == "__main__":
    main()
