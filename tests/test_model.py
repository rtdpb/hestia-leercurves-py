"""Tests for the learning-curve model.

Expected values are computed by hand from the GeoDMS ``MaakCurve`` formula so
that the port is pinned to the original model's behaviour, not just to itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hestia_leercurves import (
    AnchorCurve,
    CurveSettings,
    LearningCurveModel,
    Scenario,
)

DATA_CSV = Path(__file__).resolve().parents[1] / "data" / "leercurves.csv"


@pytest.fixture
def model() -> LearningCurveModel:
    return LearningCurveModel.from_csv(DATA_CSV)


def test_loads_all_technologies(model: LearningCurveModel) -> None:
    techs = model.technologies()
    assert len(techs) == 24
    assert "Warmtenet" in techs
    assert "hWP" in techs


def test_factor_at_reference_year_is_one(model: LearningCurveModel) -> None:
    # In 2020 nearly every curve equals its 100% reference.
    assert model.factor("hWP", 2020) == pytest.approx(1.0)


def test_default_blend_between_scenarios(model: LearningCurveModel) -> None:
    # hWP 2035: optimistic 82, pessimistic 89.5; blend at 0.5 -> 0.8575.
    assert model.factor("hWP", 2035) == pytest.approx(0.8575)


def test_optimistic_shift_selects_optimistic_curve() -> None:
    model = LearningCurveModel.from_csv(
        DATA_CSV, CurveSettings(min_max_shift=0.0)
    )
    assert model.factor("hWP", 2050) == pytest.approx(0.64)


def test_pessimistic_shift_selects_pessimistic_curve() -> None:
    model = LearningCurveModel.from_csv(
        DATA_CSV, CurveSettings(min_max_shift=1.0)
    )
    assert model.factor("hWP", 2050) == pytest.approx(0.80)


def test_learning_off_keeps_costs_constant() -> None:
    model = LearningCurveModel.from_csv(
        DATA_CSV, CurveSettings(learning_shift=0.0)
    )
    # With learning switched off every factor collapses to 1.0.
    assert model.factor("hWP", 2050) == pytest.approx(1.0)
    assert model.factor("Waterstof", 2045) == pytest.approx(1.0)


def test_clamps_beyond_last_anchor(model: LearningCurveModel) -> None:
    # 2100 clamps to 2050: optimistic 64, pessimistic 80, blend 0.5 -> 0.72.
    assert model.factor("hWP", 2100) == pytest.approx(0.72)


def test_fractional_anchor_data(model: LearningCurveModel) -> None:
    # Isolatie 2025: optimistic (96.53, 108.11) -> 102.32,
    #                pessimistic (95.15, 111.32) -> 103.235; blend 0.5.
    expected = ((102.32 + 103.235) / 2) / 100
    assert model.factor("Isolatie", 2025) == pytest.approx(expected)


def test_factors_over_multiple_years(model: LearningCurveModel) -> None:
    result = model.factors("hWP", [2020, 2035, 2050])
    assert set(result) == {2020, 2035, 2050}
    assert result[2020] == pytest.approx(1.0)


def test_unknown_technology_raises(model: LearningCurveModel) -> None:
    with pytest.raises(KeyError):
        model.factor("DoesNotExist", 2030)


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_settings_validation(bad: float) -> None:
    with pytest.raises(ValueError):
        CurveSettings(min_max_shift=bad)
    with pytest.raises(ValueError):
        CurveSettings(learning_shift=bad)


def test_anchor_curve_length_validation() -> None:
    with pytest.raises(ValueError):
        AnchorCurve(years=(2000, 2010), optimistic=(100.0,), pessimistic=(100.0, 99.0))


def test_scenario_enum_values() -> None:
    assert Scenario("optimistic") is Scenario.OPTIMISTIC
    assert Scenario("pessimistic") is Scenario.PESSIMISTIC
