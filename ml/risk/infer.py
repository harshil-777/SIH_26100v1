"""Run the trained risk model on one bid.

    model = RiskModel("ml/models/risk")          # a local dir or a downloaded Hugging Face repo
    model.predict(tender, observed)
    # -> {"risk_level", "probabilities", "top_factors": [{"feature", "value", "contribution"}]}

top_factors are LightGBM's exact per-prediction SHAP contributions (pred_contrib) toward the
predicted class, so the officer sees which observed facts drove the estimate.
"""
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np

from ml.risk.features import FEATURE_NAMES, featurize


class RiskModel:
    def __init__(self, model_dir: str):
        model_dir = Path(model_dir)
        self.booster = lgb.Booster(model_file=str(model_dir / "model.txt"))
        spec = json.loads((model_dir / "features.json").read_text())
        if spec["feature_names"] != FEATURE_NAMES:
            raise ValueError("features.json does not match this code's feature list; retrain or update the code")
        self.classes = spec["classes"]

    def predict(self, tender: dict, observed: dict, top_k: int = 5) -> dict:
        row = np.array([featurize(tender, observed)], dtype=np.float64)
        probs = self.booster.predict(row)[0]
        best = int(probs.argmax())
        # pred_contrib: per class, one contribution per feature plus a bias term.
        contrib = self.booster.predict(row, pred_contrib=True)[0]
        width = len(FEATURE_NAMES) + 1
        class_contrib = contrib[best * width : (best + 1) * width - 1]
        order = np.argsort(-np.abs(class_contrib))[:top_k]
        return {
            "risk_level": self.classes[best],
            "probabilities": {c: round(float(p), 4) for c, p in zip(self.classes, probs)},
            "top_factors": [
                {
                    "feature": FEATURE_NAMES[i],
                    "value": None if math.isnan(row[0][i]) else float(row[0][i]),
                    "contribution": round(float(class_contrib[i]), 4),
                }
                for i in order
            ],
        }
