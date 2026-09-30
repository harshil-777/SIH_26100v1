"""Loads the three trained models from ml/ (published to Hugging Face) and wraps them so a
missing dependency, no internet, or any runtime failure degrades to "model unavailable" rather
than crashing the pipeline. They assist the rule engine, which stays the decision of record:
- extraction  feeds stage 2 (OCR) instead of the regex parser, when it loads successfully
- risk        an extra "ml_risk_estimate" note attached to criterion_breakdown_json, never
              read by scoring.py -- it cannot change overall_score or risk_level
- recommendation  replaces stage 7's template only when its own guardrail (see
              ml/recommendation/infer.py) accepts the generated text

Everything here is a no-op unless ML_MODELS_ENABLED=true, so the app's default behaviour is
unchanged. The ml/ package needs to be on the Python path -- it lives at the repo root
alongside app/, so this just works when the app runs from the repo root (as it always does).
"""
import logging
import threading
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def _device() -> str | None:
    return get_settings().ml_device


@lru_cache
def _extractor():
    from ml.extraction.infer import FieldExtractor

    return FieldExtractor(get_settings().ml_extraction_model, device=_device())


@lru_cache
def _risk_model():
    from pathlib import Path

    from ml.risk.infer import RiskModel

    repo_or_path = get_settings().ml_risk_model
    if Path(repo_or_path).exists():
        # A local directory (e.g. extracted from trained_models.zip) rather than a HF repo id --
        # unlike AutoModel.from_pretrained (used by the other two models), snapshot_download only
        # understands repo ids, so it can't be handed a local path directly.
        local_dir = repo_or_path
    else:
        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(repo_or_path)
    return RiskModel(local_dir)


@lru_cache
def _recommender():
    from ml.recommendation.infer import Recommender

    return Recommender(get_settings().ml_recommendation_model, device=_device())


@lru_cache
def _load_once(name: str, loader) -> Any:
    """Loads once per process; a failure is cached too, so a broken load isn't retried on
    every request (which would mean a slow failing import on every single call)."""
    try:
        return loader()
    except Exception:
        logger.warning("ML model %r unavailable; falling back to non-ML behaviour", name, exc_info=True)
        return None


# lru_cache doesn't stop two threads racing on the same first load; without this a request
# arriving during warm_up() would start a second full copy of the same model.
_load_lock = threading.Lock()


def _get(name: str, loader) -> Any:
    with _load_lock:
        return _load_once(name, loader)


def warm_up() -> None:
    """Loads all three models up front, so the first real request doesn't pay for the
    download and load."""
    if not get_settings().ml_models_enabled:
        return
    for name, loader in (("extraction", _extractor), ("risk", _risk_model), ("recommendation", _recommender)):
        _get(name, loader)
    logger.info("ML models warmed up")


def extract_fields(text: str) -> dict | None:
    """{"fields": {...}, "confidence": {...}} from the trained extractor, or None to fall
    back to app/services/ocr.py's regex parser."""
    if not get_settings().ml_models_enabled:
        return None
    extractor = _get("extraction", _extractor)
    if extractor is None:
        return None
    try:
        return extractor.extract(text)
    except Exception:
        logger.warning("Extraction model failed on this document; falling back to regex", exc_info=True)
        return None


def facts_to_risk_input(tender, facts) -> tuple[dict, dict]:
    """app.models.Tender + app.services.rule_engine.Facts -> ml.risk.features.featurize's
    (tender, observed) shape. Facts was deliberately modeled on that shape already, so this
    is mostly a direct field rename."""
    tender_dict = {
        "msme_reserved": bool(tender.msme_reserved),
        "mii_threshold": float(tender.mii_local_content_threshold_pct or 0),
        "epfo_applicable": tender.epfo_applicable_employee_threshold is not None,
        "mandatory_docs": ["x"] * facts.completeness.total_mandatory,  # only the count is used
    }
    observed = {
        "portal": facts.portal_facts,
        "ocr": facts.ocr_facts,
        "declarations": facts.declarations,
        "missing_docs": [m.document_type for m in facts.completeness.missing],
        "employees": facts.bidder_employee_count,
    }
    return tender_dict, observed


def risk_estimate(tender, facts) -> dict | None:
    """{"risk_level", "probabilities", "top_factors"} from the trained model, or None."""
    if not get_settings().ml_models_enabled:
        return None
    model = _get("risk", _risk_model)
    if model is None:
        return None
    try:
        tender_dict, observed = facts_to_risk_input(tender, facts)
        return model.predict(tender_dict, observed)
    except Exception:
        logger.warning("Risk model failed on this bid; omitting ml_risk_estimate", exc_info=True)
        return None


def recommend(overall_score, risk_level: str, breakdown: dict) -> dict | None:
    """{"text", "source", "problems"} from the trained model (with its own guardrail against
    a wrong verdict or an invented/missing finding), or None to fall back to
    app/services/recommendation.py's deterministic text."""
    if not get_settings().ml_models_enabled:
        return None
    recommender = _get("recommendation", _recommender)
    if recommender is None:
        return None
    try:
        return recommender.generate_with_check(overall_score, risk_level, breakdown)
    except Exception:
        logger.warning("Recommendation model failed on this bid; falling back to template text", exc_info=True)
        return None
