"""Hugging Face Inference Endpoint custom handler for the gem-bid-risk model.

LightGBM isn't one of HF's auto-detected model types, so a custom handler is required
(Endpoint task: "Custom"). This file is uploaded to the repo root alongside model.txt,
features.json and features.py (already placed there by ml/push_to_hub.py), and HF loads
it as EndpointHandler at container start.

Request body:
    {"inputs": {"tender": {...}, "observed": {...}}}
  (see ml/risk/sampler.py's docstring for the exact tender/observed shape)

Response: a one-item list (HF's Inference Endpoint convention), matching
ml/risk/infer.py's RiskModel.predict() output:
    [{"risk_level": "...", "probabilities": {...}, "top_factors": [...]}]
"""
import json
import math
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np

from features import FEATURE_NAMES, featurize  # flat file alongside this one in the repo


class EndpointHandler:
    def __init__(self, path: str = ""):
        root = Path(path)
        self.booster = lgb.Booster(model_file=str(root / "model.txt"))
        spec = json.loads((root / "features.json").read_text())
        if spec["feature_names"] != FEATURE_NAMES:
            raise ValueError("features.json does not match this handler's feature list")
        self.classes = spec["classes"]

    def __call__(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        inputs = data.get("inputs", data)
        tender, observed = inputs["tender"], inputs["observed"]

        row = np.array([featurize(tender, observed)], dtype=np.float64)
        probs = self.booster.predict(row)[0]
        best = int(probs.argmax())

        contrib = self.booster.predict(row, pred_contrib=True)[0]
        width = len(FEATURE_NAMES) + 1
        class_contrib = contrib[best * width : (best + 1) * width - 1]
        order = np.argsort(-np.abs(class_contrib))[:5]

        return [{
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
        }]
