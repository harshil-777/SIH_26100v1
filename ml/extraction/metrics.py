"""Entity-level precision/recall/F1 over BIO tag sequences (exact span + label match)."""
from collections import Counter


def bio_entities(tags: list[str]) -> set[tuple[str, int, int]]:
    """['B-GSTIN','I-GSTIN','O',...] -> {(label, start_index, end_index_exclusive)}.

    A stray I- tag with no matching B- starts a new entity, which is how the model's output
    is decoded at inference time too.
    """
    entities, label, start = set(), None, 0
    for i, tag in enumerate([*tags, "O"]):
        prefix, _, tag_label = tag.partition("-")
        continues = prefix == "I" and tag_label == label
        if label is not None and not continues:
            entities.add((label, start, i))
            label = None
        if prefix in ("B", "I") and not continues:
            label, start = tag_label, i
    return entities


def entity_scores(gold: list[list[str]], pred: list[list[str]]) -> dict:
    tp, fp, fn = Counter(), Counter(), Counter()
    for g_tags, p_tags in zip(gold, pred):
        g, p = bio_entities(g_tags), bio_entities(p_tags)
        for label, *_ in g & p:
            tp[label] += 1
        for label, *_ in p - g:
            fp[label] += 1
        for label, *_ in g - p:
            fn[label] += 1

    def prf(t: int, f_p: int, f_n: int) -> dict:
        precision = t / (t + f_p) if t + f_p else 0.0
        recall = t / (t + f_n) if t + f_n else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "support": t + f_n}

    labels = sorted(set(tp) | set(fp) | set(fn))
    return {
        "micro": prf(sum(tp.values()), sum(fp.values()), sum(fn.values())),
        "per_label": {label: prf(tp[label], fp[label], fn[label]) for label in labels},
    }
