"""Tests for the piecewise-linear interpolation helper."""

from __future__ import annotations

import pytest

from hestia_leercurves.interpolation import interpolate_linear

YEARS = (2000, 2010, 2020, 2030, 2040, 2050)
VALUES = (117.0, 109.0, 100.0, 88.0, 76.0, 64.0)  # hWP optimistic anchors


def test_returns_anchor_value_at_anchor_year() -> None:
    assert interpolate_linear(2020, YEARS, VALUES) == 100.0
    assert interpolate_linear(2050, YEARS, VALUES) == 64.0


def test_interpolates_midpoint() -> None:
    # Halfway between 2030 (88) and 2040 (76) -> 82.
    assert interpolate_linear(2035, YEARS, VALUES) == pytest.approx(82.0)


def test_interpolates_arbitrary_fraction() -> None:
    # 2032 is 20% from 2030 (88) towards 2040 (76): 88 - 0.2 * 12 = 85.6.
    assert interpolate_linear(2032, YEARS, VALUES) == pytest.approx(85.6)


def test_clamps_below_range() -> None:
    assert interpolate_linear(1990, YEARS, VALUES) == 117.0


def test_clamps_above_range() -> None:
    assert interpolate_linear(2100, YEARS, VALUES) == 64.0


def test_single_anchor_is_constant() -> None:
    assert interpolate_linear(2025, (2020,), (42.0,)) == 42.0


@pytest.mark.parametrize(
    "xs, ys",
    [
        ((2000, 2010), (1.0,)),  # length mismatch
        ((), ()),  # empty
        ((2010, 2000), (1.0, 2.0)),  # not increasing
        ((2000, 2000), (1.0, 2.0)),  # not strictly increasing
    ],
)
def test_invalid_anchors_raise(xs: tuple[float, ...], ys: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        interpolate_linear(2005, xs, ys)
