"""Write an officer recommendation with the trained model.

    recommender = Recommender("ml/models/recommendation")   # or a Hugging Face repo id
    recommender.generate(overall_score, risk_level, breakdown)

Same signature as app/services/recommendation.py's generate_recommendation, and the output
always carries the "AI-generated, advisory only:" label, even if the model were to drop it.

Guardrail: a small generative model can occasionally state the wrong verdict, drop a finding
or invent one -- and wrong advice to a procurement officer is worse than plain advice. Every
generated text is graded against the input's own findings (ml/recommendation/metrics.py); if it
fails, the deterministic template text for the same findings is returned instead, which is
correct by construction. `generate_with_check` reports which one was used.
"""
import random

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from ml.recommendation.findings import build_input, finding_key, findings_from_breakdown, verdict
from ml.recommendation.metrics import grade
from ml.recommendation.targets import PREFIX, write_target


class Recommender:
    # Greedy decoding (num_beams=1) by default: on 120 fresh rule-engine-scored bids it passed the
    # guardrail 120/120, same as 4-beam search, at ~40% less CPU time per call.
    def __init__(self, model_path: str, device: str | None = None, max_input: int = 256, max_target: int = 256,
                 num_beams: int = 1):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).eval()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.max_input, self.max_target, self.num_beams = max_input, max_target, num_beams

    @torch.no_grad()
    def _model_text(self, overall_score, risk_level: str, breakdown: dict) -> str:
        enc = self.tokenizer(
            build_input(overall_score, risk_level, breakdown),
            truncation=True, max_length=self.max_input, return_tensors="pt",
        )
        ids = self.model.generate(**{k: v.to(self.device) for k, v in enc.items()},
                                  max_new_tokens=self.max_target, num_beams=self.num_beams)
        text = self.tokenizer.decode(ids[0], skip_special_tokens=True).strip()
        return text if text.startswith(PREFIX.strip()) else PREFIX + text

    def generate_with_check(self, overall_score, risk_level: str, breakdown: dict) -> dict:
        """{"text", "source": "model" | "template_fallback", "problems"}."""
        findings = findings_from_breakdown(breakdown)
        keys = sorted({finding_key(f) for f in findings})
        text = self._model_text(overall_score, risk_level, breakdown)
        g = grade(text, verdict(risk_level, findings), keys)
        problems = []
        if not g["verdict_correct"]:
            problems.append("wrong verdict")
        if g["findings_mentioned"] < len(keys):
            problems.append("finding(s) not mentioned")
        if g["invented"]:
            problems.append(f"invented finding(s): {', '.join(g['invented'])}")
        if not problems:
            return {"text": text, "source": "model", "problems": []}
        # Seeded, so the same breakdown always yields the same fallback wording.
        fallback = write_target(random.Random(0), overall_score, risk_level, findings)
        return {"text": fallback, "source": "template_fallback", "problems": problems}

    def generate(self, overall_score, risk_level: str, breakdown: dict) -> str:
        return self.generate_with_check(overall_score, risk_level, breakdown)["text"]
