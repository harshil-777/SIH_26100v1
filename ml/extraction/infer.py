"""Run the trained extraction model over OCR text.

    extractor = FieldExtractor("ml/models/extraction")   # or a Hugging Face repo id
    extractor.extract(text)  # -> {"fields": {...}, "confidence": {...}}

"fields" has the same names and value shapes as app/services/ocr.py's parse_fields, so it can
stand in for the regex parser in stage 2.
"""
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from ml.extraction.fields import LABEL_TO_FIELD, normalize


class FieldExtractor:
    def __init__(self, model_path: str, device: str | None = None, max_length: int = 512, stride: int = 96):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(model_path).eval()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.id2label = self.model.config.id2label
        self.max_length, self.stride = max_length, stride

    @torch.no_grad()
    def _token_predictions(self, text: str) -> list[tuple[int, int, str, float]]:
        """(char_start, char_end, tag, prob) per token, merged across overlapping windows."""
        enc = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            stride=self.stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding=True,
            return_tensors="pt",
        )
        offsets = enc.pop("offset_mapping")
        enc.pop("overflow_to_sample_mapping", None)
        probs = self.model(**{k: v.to(self.device) for k, v in enc.items()}).logits.softmax(-1).cpu()

        best: dict[tuple[int, int], tuple[str, float]] = {}
        for window_offsets, window_probs in zip(offsets.tolist(), probs):
            confidence, tag_ids = window_probs.max(-1)
            for (start, end), tag_id, p in zip(window_offsets, tag_ids.tolist(), confidence.tolist()):
                if start == end:
                    continue
                # A token seen in two windows keeps its more confident prediction.
                if (start, end) not in best or p > best[(start, end)][1]:
                    best[(start, end)] = (self.id2label[tag_id], p)
        return [(s, e, tag, p) for (s, e), (tag, p) in sorted(best.items())]

    def extract(self, text: str) -> dict:
        entities = []  # (label, char_start, char_end, [probs])
        for start, end, tag, p in self._token_predictions(text):
            prefix, _, label = tag.partition("-")
            if prefix == "I" and entities and entities[-1][0] == label and entities[-1][2] <= start:
                entities[-1][2] = end
                entities[-1][3].append(p)
            elif prefix in ("B", "I"):
                entities.append([label, start, end, [p]])

        fields, confidence = {}, {}
        for label, start, end, ps in entities:
            field = LABEL_TO_FIELD[label]
            value = normalize(field, text[start:end])
            score = sum(ps) / len(ps)
            # One value per field, like the regex parser: keep the most confident mention.
            if value is not None and score > confidence.get(field, 0.0):
                fields[field], confidence[field] = value, round(score, 4)
        return {"fields": fields, "confidence": confidence}
