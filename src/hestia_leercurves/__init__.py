"""A clean, tested Python port of Hestia's learning-curve ("leercurve") logic.

See the project README for the mapping from the original GeoDMS source to this
package.
"""

from __future__ import annotations

from .interpolation import interpolate_linear
from .model import AnchorCurve, CurveSettings, LearningCurveModel, Scenario

__all__ = [
    "AnchorCurve",
    "CurveSettings",
    "LearningCurveModel",
    "Scenario",
    "interpolate_linear",
]

__version__ = "0.1.0"
