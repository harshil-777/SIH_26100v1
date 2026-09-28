"""Compose document text while recording exact character spans for labelled entities.

OCR-style corruption is applied per segment as the text is built, so span offsets always
point at exactly the characters that ended up in the final text -- no re-alignment needed.
"""
import random

# Confusions a real OCR engine makes on printed certificates.
_CONFUSIONS = {
    "O": "0", "0": "O", "I": "1", "1": "I", "l": "1", "S": "5", "5": "S",
    "B": "8", "8": "B", "Z": "2", "2": "Z", "G": "6", "e": "c", "m": "rn",
}


class DocBuilder:
    def __init__(self, rng: random.Random, doc_type: str, noise: float = 0.0, uppercase: bool = False):
        self.rng = rng
        self.doc_type = doc_type
        self.noise = noise  # per-character corruption probability for plain text
        self.uppercase = uppercase
        self._parts: list[str] = []
        self._pos = 0
        self.spans: list[tuple[int, int, str]] = []

    def _corrupt(self, s: str, rate: float) -> str:
        if self.uppercase:
            s = s.upper()
        if rate <= 0:
            return s
        out = []
        for ch in s:
            roll = self.rng.random()
            if roll < rate and ch in _CONFUSIONS:
                out.append(_CONFUSIONS[ch])
            elif roll < rate * 1.3 and ch == " ":
                out.append("  ")  # doubled gap between OCR'd words
            else:
                out.append(ch)
        return "".join(out)

    def text(self, s: str) -> "DocBuilder":
        s = self._corrupt(s, self.noise)
        self._parts.append(s)
        self._pos += len(s)
        return self

    def ent(self, label: str, value: str) -> "DocBuilder":
        # Identifiers are printed crisply; they get a fifth of the background noise rate.
        value = self._corrupt(value, self.noise / 5)
        self.spans.append((self._pos, self._pos + len(value), label))
        self._parts.append(value)
        self._pos += len(value)
        return self

    def line(self, *pieces: tuple[str, str] | str) -> "DocBuilder":
        """A line of plain strings and (label, value) entity tuples, then a newline."""
        for piece in pieces:
            if isinstance(piece, tuple):
                self.ent(*piece)
            else:
                self.text(piece)
        # Layout loss: OCR sometimes runs two lines together.
        self._parts.append(" " if self.noise and self.rng.random() < self.noise * 10 else "\n")
        self._pos += 1
        return self

    def build(self) -> dict:
        text = "".join(self._parts)
        for start, end, _ in self.spans:
            assert 0 <= start < end <= len(text), "span out of bounds"
        return {"doc_type": self.doc_type, "text": text, "spans": [list(s) for s in self.spans]}
