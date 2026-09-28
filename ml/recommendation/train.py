"""Fine-tune a small seq2seq model to write officer recommendations from score breakdowns.

    python -m ml.recommendation.train                                   # full run (GPU)
    python -m ml.recommendation.train --limit 300 --epochs 1 --eval-examples 20   # CPU smoke test

Reads ml/data/recommendation/*.jsonl and writes a Hugging Face model directory to
ml/models/recommendation, plus metrics.json from *generated* test outputs (see metrics.py).
"""
import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
    set_seed,
)

from ml.common.io import DATA_DIR, MODELS_DIR, read_jsonl
from ml.recommendation.metrics import grade, summarize


class PairDataset(Dataset):
    def __init__(self, rows: list[dict], tokenizer, max_input: int, max_target: int):
        self.items = []
        for row in rows:
            enc = tokenizer(row["input"], truncation=True, max_length=max_input)
            enc["labels"] = tokenizer(text_target=row["target"], truncation=True, max_length=max_target)["input_ids"]
            self.items.append(dict(enc))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict:
        return self.items[i]


@torch.no_grad()
def generate(model, tokenizer, inputs: list[str], max_input: int, max_target: int, batch_size: int = 16) -> list[str]:
    model.eval()
    outputs = []
    for i in range(0, len(inputs), batch_size):
        enc = tokenizer(inputs[i : i + batch_size], truncation=True, max_length=max_input, padding=True, return_tensors="pt")
        ids = model.generate(**{k: v.to(model.device) for k, v in enc.items()}, max_new_tokens=max_target, num_beams=4)
        outputs += tokenizer.batch_decode(ids, skip_special_tokens=True)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DATA_DIR / "recommendation"))
    parser.add_argument("--out", default=str(MODELS_DIR / "recommendation"))
    parser.add_argument("--base-model", default="google/flan-t5-small")
    parser.add_argument("--epochs", type=float, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--max-input", type=int, default=256)
    parser.add_argument("--max-target", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None, help="cap examples per split (smoke tests)")
    parser.add_argument("--eval-examples", type=int, default=1000, help="test examples to generate and grade")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    set_seed(args.seed)
    data, out = Path(args.data), Path(args.out)
    rows = {s: list(read_jsonl(data / f"{s}.jsonl"))[: args.limit] for s in ("train", "validation", "test")}
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.base_model)

    too_long = sum(len(tokenizer(r["target"])["input_ids"]) > args.max_target for r in rows["train"])
    print(f"train {len(rows['train'])}, validation {len(rows['validation'])}; {too_long} targets exceed {args.max_target} tokens")

    training_args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=0.05,  # transformers 5: a float in [0, 1) is a ratio of total steps
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=50,
        report_to="none",
        seed=args.seed,
        # T5 is numerically unstable in fp16; bf16 is fine where the GPU supports it.
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=PairDataset(rows["train"], tokenizer, args.max_input, args.max_target),
        eval_dataset=PairDataset(rows["validation"], tokenizer, args.max_input, args.max_target),
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    trainer.train()

    test = rows["test"][: args.eval_examples]
    outputs = generate(trainer.model, tokenizer, [r["input"] for r in test], args.max_input, args.max_target)
    grades = [grade(o, r["verdict"], r["finding_keys"]) for o, r in zip(outputs, test)]
    metrics = {"test": summarize(grades), "args": vars(args)}
    samples = [{"input": r["input"], "output": o, "reference": r["target"]} for r, o in zip(test[:20], outputs)]

    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "samples.json").write_text(json.dumps(samples, indent=2))
    print(json.dumps(metrics["test"], indent=2))
    print(f"model saved to {out}")


if __name__ == "__main__":
    main()
