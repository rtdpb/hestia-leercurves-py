"""Piecewise-linear interpolation with constant extrapolation.

This mirrors the behaviour of GeoDMS' ``interpolate_linear`` as it is used in
Hestia's ``MaakCurve`` template: between the anchor points the value is
interpolated linearly, and outside the anchor range the value is clamped to the
nearest endpoint (constant extrapolation). This matches the behaviour of the
public GeoDMS source; the exact extrapolation behaviour of the closed model
should still be confirmed against a running GeoDMS reference.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["interpolate_linear"]


def interpolate_linear(
    x: float,
    xs: Sequence[float],
    ys: Sequence[float],
) -> float:
    """Return the piecewise-linear value of ``ys`` at ``x`` over anchors ``xs``.

    Args:
        x: The position to evaluate (e.g. a calendar year).
        xs: Strictly increasing anchor positions (e.g. the anchor years).
        ys: The values at each anchor; must be the same length as ``xs``.

    Returns:
        The interpolated value. For ``x`` outside ``[xs[0], xs[-1]]`` the
        nearest endpoint value is returned (constant extrapolation), matching
        GeoDMS ``interpolate_linear``.

    Raises:
        ValueError: If ``xs`` and ``ys`` differ in length, are empty, or if
            ``xs`` is not strictly increasing.
    """
    if len(xs) != len(ys):
        raise ValueError(f"xs and ys must be equal length, got {len(xs)} and {len(ys)}")
    if len(xs) == 0:
        raise ValueError("xs and ys must contain at least one anchor")
    if any(b <= a for a, b in zip(xs, xs[1:], strict=False)):
        raise ValueError(f"xs must be strictly increasing, got {list(xs)}")

    # Constant extrapolation outside the anchor range.
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])

    # Locate the segment [xs[i], xs[i + 1]] that contains x and interpolate.
    for i in range(len(xs) - 1):
        left, right = xs[i], xs[i + 1]
        if left <= x <= right:
            weight = (x - left) / (right - left)
            return float(ys[i]) + weight * (float(ys[i + 1]) - float(ys[i]))

    # Unreachable: the boundary checks above cover every remaining case.
    raise AssertionError("interpolation segment not found")  # pragma: no cover
