"""BUILD_SPEC section 8's scoring rule."""
import pytest

from app.services.scoring import compute_score
from tests.unit.factories import graded, mandatory


def test_weighted_average_of_graded_criteria_is_normalised_by_total_weight():
    score, risk, breakdown = compute_score([graded("a", 100, 0.10), graded("b", 66.67, 0.25)])
    assert score == pytest.approx(76.19, abs=0.01)
    assert risk == "Medium"
    assert breakdown["mandatory_failure_reasons"] == []


@pytest.mark.parametrize(
    ("value", "band"),
    [(100, "Low"), (85, "Low"), (84.99, "Medium"), (60, "Medium"), (59.99, "High"), (0, "High")],
)
def test_risk_bands_boundaries(value, band):
    assert compute_score([graded("a", value, 1.0)])[1] == band


def test_mandatory_failure_caps_at_40_and_is_non_compliant_even_with_perfect_graded_scores():
    score, risk, breakdown = compute_score([mandatory("gst_active", False, "GSTN cancelled."), graded("a", 100, 1.0)])
    assert (score, risk) == (40.0, "Non-Compliant")
    assert breakdown["mandatory_failure_reasons"] == ["GSTN cancelled."]


def test_mandatory_failure_keeps_a_graded_score_already_below_the_cap():
    assert compute_score([mandatory("pan_valid", False), graded("a", 28.57, 1.0)])[:2] == (28.57, "Non-Compliant")


def test_no_graded_criteria_scores_100():
    assert compute_score([mandatory("gst_active", True)])[:2] == (100.0, "Low")
