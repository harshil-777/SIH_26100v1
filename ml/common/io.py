import json
from collections.abc import Iterable, Iterator
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def split_sizes(n: int, val_frac: float = 0.05, test_frac: float = 0.05) -> dict[str, int]:
    val, test = max(1, int(n * val_frac)), max(1, int(n * test_frac))
    return {"train": n - val - test, "validation": val, "test": test}
