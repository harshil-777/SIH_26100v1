"""Fine-tune a token-classification model to extract certificate fields.

    python -m ml.extraction.train                      # full run (use a GPU: Colab/Kaggle)
    python -m ml.extraction.train --limit 400 --epochs 1 --max-length 256   # CPU smoke test

Reads ml/data/extraction/*.jsonl (from ml.extraction.generate) and writes a Hugging Face
model directory (weights, tokenizer, label map, metrics.json) to ml/models/extraction.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
    set_seed,
)

from ml.common.io import DATA_DIR, MODELS_DIR, read_jsonl
from ml.extraction.fields import BIO_TAGS
from ml.extraction.metrics import entity_scores

TAG_TO_ID = {tag: i for i, tag in enumerate(BIO_TAGS)}
IGNORE = -100


def token_tags(offsets: list[tuple[int, int]], spans: list[list]) -> list[int]:
    """Char spans -> one BIO tag id per token; special/padding tokens get IGNORE.

    A token belongs to a span if it overlaps it; the first such token is B-, later ones I-.
    """
    tags, seen = [], set()
    for start, end in offsets:
        if start == end:  # special token
            tags.append(IGNORE)
            continue
        tag = "O"
        for i, (s_start, s_end, label) in enumerate(spans):
            if start < s_end and end > s_start:
                tag = f"{'I' if i in seen else 'B'}-{label}"
                seen.add(i)
                break
        tags.append(TAG_TO_ID[tag])
    return tags


class CertificateDataset(Dataset):
    def __init__(self, path: Path, tokenizer, max_length: int, limit: int | None = None):
        self.items = []
        self.truncated_entities = 0
        for n, row in enumerate(read_jsonl(path)):
            if limit is not None and n >= limit:
                break
            enc = tokenizer(row["text"], truncation=True, max_length=max_length, return_offsets_mapping=True)
            offsets = enc.pop("offset_mapping")
            last_char = max(e for _, e in offsets)
            self.truncated_entities += sum(1 for s, _, _ in row["spans"] if s >= last_char)
            enc["labels"] = token_tags(offsets, row["spans"])
            self.items.append(dict(enc))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict:
        return self.items[i]


def _to_tags(label_ids: np.ndarray, predictions: np.ndarray) -> tuple[list[list[str]], list[list[str]]]:
    gold, pred = [], []
    for g_row, p_row in zip(label_ids, predictions):
        keep = g_row != IGNORE
        gold.append([BIO_TAGS[t] for t in g_row[keep]])
        pred.append([BIO_TAGS[t] for t in p_row[keep]])
    return gold, pred


def compute_metrics(eval_pred) -> dict:
    logits, label_ids = eval_pred
    gold, pred = _to_tags(label_ids, logits.argmax(-1))
    micro = entity_scores(gold, pred)["micro"]
    return {"entity_precision": micro["precision"], "entity_recall": micro["recall"], "entity_f1": micro["f1"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DATA_DIR / "extraction"))
    parser.add_argument("--out", default=str(MODELS_DIR / "extraction"))
    parser.add_argument("--base-model", default="distilbert-base-cased")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--limit", type=int, default=None, help="cap examples per split (smoke tests)")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    set_seed(args.seed)
    data, out = Path(args.data), Path(args.out)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    splits = {
        split: CertificateDataset(data / f"{split}.jsonl", tokenizer, args.max_length, args.limit)
        for split in ("train", "validation", "test")
    }
    for split, ds in splits.items():
        print(f"{split}: {len(ds)} documents, {ds.truncated_entities} entities lost to truncation")

    model = AutoModelForTokenClassification.from_pretrained(
        args.base_model,
        num_labels=len(BIO_TAGS),
        id2label=dict(enumerate(BIO_TAGS)),
        label2id=TAG_TO_ID,
    )
    training_args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=0.06,  # transformers 5: a float in [0, 1) is a ratio of total steps
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="entity_f1",
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        report_to="none",
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=splits["train"],
        eval_dataset=splits["validation"],
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=compute_metrics,
    )
    trainer.train()

    test = trainer.predict(splits["test"])
    gold, pred = _to_tags(test.label_ids, test.predictions.argmax(-1))
    metrics = {"test": entity_scores(gold, pred), "args": vars(args)}

    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics["test"]["micro"], indent=2))
    print(f"model saved to {out}")


if __name__ == "__main__":
    main()
