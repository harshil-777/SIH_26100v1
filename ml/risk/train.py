"""Train the bid risk model (LightGBM, multiclass) on the synthetic bids.

    python -m ml.risk.train

Writes ml/models/risk/: model.txt (LightGBM's plain-text format -- no pickle), features.json
(feature order and categorical codes), metrics.json. CPU is plenty.

Reported alongside the model's accuracy: the rule engine's accuracy when run on the same noisy
observations. The gap between the two is what the model adds -- recognising when missing or
misread data, not the bidder, is behind a failing verdict.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np

from ml.common.io import DATA_DIR, MODELS_DIR, read_jsonl
from ml.risk.features import CATEGORICAL_FEATURES, CATEGORY_CODES, FEATURE_NAMES, STATUS_CODES, featurize

CLASSES = ["Low", "Medium", "High", "Non-Compliant"]


def load(path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    x, y, rules = [], [], []
    for row in read_jsonl(path):
        x.append(featurize(row["tender"], row["observed"]))
        y.append(CLASSES.index(row["label"]))
        rules.append(row["rules_on_observed"])
    return np.array(x, dtype=np.float64), np.array(y), rules


def report(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    confusion = [[int(((y_true == t) & (y_pred == p)).sum()) for p in range(len(CLASSES))] for t in range(len(CLASSES))]
    per_class = {}
    for i, name in enumerate(CLASSES):
        tp = confusion[i][i]
        precision = tp / max(1, sum(confusion[r][i] for r in range(len(CLASSES))))
        recall = tp / max(1, sum(confusion[i]))
        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "support": int(sum(confusion[i])),
        }
    return {
        "accuracy": round(float((y_true == y_pred).mean()), 4),
        "macro_f1": round(float(np.mean([c["f1"] for c in per_class.values()])), 4),
        "per_class": per_class,
        "confusion_matrix": {"labels": CLASSES, "rows_true_cols_pred": confusion},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DATA_DIR / "risk"))
    parser.add_argument("--out", default=str(MODELS_DIR / "risk"))
    parser.add_argument("--rounds", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    data, out = Path(args.data), Path(args.out)
    x_train, y_train, _ = load(data / "train.jsonl")
    x_val, y_val, _ = load(data / "validation.jsonl")
    x_test, y_test, rules_test = load(data / "test.jsonl")
    print(f"train {len(y_train)}, validation {len(y_val)}, test {len(y_test)} bids; {len(FEATURE_NAMES)} features")

    # Balanced class weights so the rare High band isn't drowned out by Low/Non-Compliant.
    counts = Counter(y_train.tolist())
    weights = np.array([len(y_train) / (len(CLASSES) * counts[c]) for c in y_train])
    params = {
        "objective": "multiclass",
        "num_class": len(CLASSES),
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_data_in_leaf": 40,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "seed": args.seed,
        "verbose": -1,
    }
    categorical = [FEATURE_NAMES.index(f) for f in CATEGORICAL_FEATURES]
    train_set = lgb.Dataset(x_train, y_train, weight=weights, feature_name=FEATURE_NAMES, categorical_feature=categorical)
    val_set = lgb.Dataset(x_val, y_val, reference=train_set)
    booster = lgb.train(
        params, train_set, num_boost_round=args.rounds, valid_sets=[val_set],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
    )

    y_pred = booster.predict(x_test, num_iteration=booster.best_iteration).argmax(1)
    rules_pred = np.array([CLASSES.index(r) for r in rules_test])
    importance = booster.feature_importance("gain")
    metrics = {
        "model_on_observed": report(y_test, y_pred),
        "rule_engine_on_observed": report(y_test, rules_pred),
        "best_iteration": booster.best_iteration,
        "top_features_by_gain": sorted(
            ({"feature": f, "gain": round(float(g), 1)} for f, g in zip(FEATURE_NAMES, importance)),
            key=lambda r: -r["gain"],
        )[:15],
        "args": vars(args),
    }

    out.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out / "model.txt"), num_iteration=booster.best_iteration)
    (out / "features.json").write_text(json.dumps({
        "feature_names": FEATURE_NAMES,
        "categorical_features": CATEGORICAL_FEATURES,
        "status_codes": STATUS_CODES,
        "category_codes": CATEGORY_CODES,
        "classes": CLASSES,
    }, indent=2))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    for name in ("model_on_observed", "rule_engine_on_observed"):
        m = metrics[name]
        print(f"{name:<24} accuracy {m['accuracy']:.4f}  macro-F1 {m['macro_f1']:.4f}")
    print(f"model saved to {out}")


if __name__ == "__main__":
    main()
