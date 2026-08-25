"""Object-oriented port of Hestia's learning-curve ("leercurve") logic.

The Hestia model (written in GeoDMS) expresses the cost development of building
technologies as *learning curves*: relative cost factors per technology,
anchored at the years 2000, 2010, ... 2050, for both an optimistic and a
pessimistic scenario. For a given view year ("zichtjaar") the model:

1. interpolates the optimistic and pessimistic factors linearly to that year;
2. blends them with a min/max shift (``min_max_shift``: 0 = optimistic,
   1 = pessimistic);
3. optionally dampens the effect with a learning shift (``learning_shift``:
   0 = costs stay constant, 1 = the full curve is applied).

This module reproduces that computation. The reference GeoDMS source is the
``MaakCurve`` template in ``model/stam/CalculationSchemes.dms`` (lines 104-114)
of the public Hestia repository; the mapping is documented in the project
README.
"""

from __future__ import annotations

import csv
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from importlib import resources
from pathlib import Path

from .interpolation import interpolate_linear

__all__ = ["Scenario", "CurveSettings", "AnchorCurve", "LearningCurveModel"]

_DEFAULT_SETTINGS_RESOURCE = "default_settings.toml"


@lru_cache(maxsize=1)
def _default_settings() -> dict[str, float]:
    """Load the bundled default shift values from ``default_settings.toml``.

    Kept in a config file (the single source of truth) rather than hard-coded,
    mirroring the GeoDMS ``DefaultSettings/Basis.dms`` layer of the model.
    """
    resource = resources.files(__package__).joinpath(_DEFAULT_SETTINGS_RESOURCE)
    with resource.open("rb") as handle:
        return dict(tomllib.load(handle)["curve"])


class Scenario(str, Enum):
    """Cost-development scenario for a learning curve."""

    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"


@dataclass(frozen=True)
class CurveSettings:
    """Scenario "shifts" that control how a learning curve is applied.

    These mirror the ``Schuiven`` parameters in Hestia:

    * ``min_max_shift`` -> ``LeercurveMinMaxSchuif``
      (0.0 = optimistic curve, 1.0 = pessimistic curve).
    * ``learning_shift`` -> ``LeercurveGebruikSchuif``
      (0.0 = costs constant at 100%, 1.0 = learning curve fully in use).

    The default values are loaded from the bundled ``default_settings.toml``
    (which mirrors the public Hestia ``DefaultSettings/Basis.dms``), so no shift
    values are hard-coded in Python. Load your own file with :meth:`from_toml`.
    """

    min_max_shift: float = field(
        default_factory=lambda: _default_settings()["min_max_shift"]
    )
    learning_shift: float = field(
        default_factory=lambda: _default_settings()["learning_shift"]
    )

    @classmethod
    def from_toml(cls, path: str | Path) -> "CurveSettings":
        """Build settings from a TOML file with a ``[curve]`` table.

        Missing keys fall back to the bundled defaults, so a config file may
        override just one shift.
        """
        with Path(path).open("rb") as handle:
            curve = tomllib.load(handle).get("curve", {})
        defaults = _default_settings()
        return cls(
            min_max_shift=float(curve.get("min_max_shift", defaults["min_max_shift"])),
            learning_shift=float(curve.get("learning_shift", defaults["learning_shift"])),
        )

    def __post_init__(self) -> None:
        for name, value in (
            ("min_max_shift", self.min_max_shift),
            ("learning_shift", self.learning_shift),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class AnchorCurve:
    """Anchor cost factors (in percent) for one technology.

    ``optimistic`` and ``pessimistic`` hold the cost factor at each year in
    ``years``. A value of 100 means "equal to the 2020 reference cost".
    """

    years: tuple[int, ...]
    optimistic: tuple[float, ...]
    pessimistic: tuple[float, ...]

    def __post_init__(self) -> None:
        if not (len(self.years) == len(self.optimistic) == len(self.pessimistic)):
            raise ValueError(
                "years, optimistic and pessimistic must have equal length "
                f"({len(self.years)}, {len(self.optimistic)}, {len(self.pessimistic)})"
            )
        if len(self.years) == 0:
            raise ValueError("an AnchorCurve needs at least one anchor year")


class LearningCurveModel:
    """Compute learning-curve cost factors for Hestia technologies.

    Example (illustrative; assumes the model was built from the bundled data):

        model = LearningCurveModel.from_csv("data/leercurves.csv")
        model.factor("hWP", 2035)   # -> 0.8575 with the default settings
    """

    def __init__(
        self,
        curves: Mapping[str, AnchorCurve],
        settings: CurveSettings | None = None,
    ) -> None:
        if not curves:
            raise ValueError("at least one learning curve is required")
        self._curves: dict[str, AnchorCurve] = dict(curves)
        self.settings: CurveSettings = settings or CurveSettings()

    # -- construction ---------------------------------------------------------

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        settings: CurveSettings | None = None,
    ) -> "LearningCurveModel":
        """Build a model from a tidy CSV with the columns produced by the port.

        Expected columns: ``technology``, ``scenario`` (``optimistic`` /
        ``pessimistic``), followed by one column per anchor year.
        """
        path = Path(path)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                raise ValueError(f"{path} is empty")
            year_columns = [c.strip() for c in header[2:]]
            years = tuple(int(c) for c in year_columns)

            optimistic: dict[str, tuple[float, ...]] = {}
            pessimistic: dict[str, tuple[float, ...]] = {}
            for row in reader:
                if not row or not row[0].strip():
                    continue
                technology = row[0].strip()
                scenario = Scenario(row[1].strip())
                values = tuple(float(v) for v in row[2 : 2 + len(years)])
                target = optimistic if scenario is Scenario.OPTIMISTIC else pessimistic
                target[technology] = values

        curves: dict[str, AnchorCurve] = {}
        for technology in optimistic.keys() | pessimistic.keys():
            if technology not in optimistic or technology not in pessimistic:
                raise ValueError(
                    f"technology {technology!r} is missing an optimistic or "
                    "pessimistic row"
                )
            curves[technology] = AnchorCurve(
                years=years,
                optimistic=optimistic[technology],
                pessimistic=pessimistic[technology],
            )
        return cls(curves, settings)

    # -- queries --------------------------------------------------------------

    def technologies(self) -> list[str]:
        """Return the available technology names, sorted alphabetically."""
        return sorted(self._curves)

    def factor(self, technology: str, year: int) -> float:
        """Return the cost factor for ``technology`` in ``year`` (1.0 = 100%).

        Reproduces the GeoDMS ``MaakCurve`` template:

            CurveMin = interpolate_linear(year, years, optimistic) / 100
            CurveMax = interpolate_linear(year, years, pessimistic) / 100
            Base     = CurveMin * (1 - s) + CurveMax * s        # s = min_max_shift
            Curve    = Base * learning_shift + 1 * (1 - learning_shift)
        """
        curve = self._get(technology)

        optimistic = interpolate_linear(year, curve.years, curve.optimistic) / 100.0
        pessimistic = interpolate_linear(year, curve.years, curve.pessimistic) / 100.0

        shift = self.settings.min_max_shift
        base = optimistic * (1.0 - shift) + pessimistic * shift

        learning = self.settings.learning_shift
        return base * learning + 1.0 * (1.0 - learning)

    def factors(self, technology: str, years: Iterable[int]) -> dict[int, float]:
        """Return ``{year: factor}`` for a technology across several years."""
        return {year: self.factor(technology, year) for year in years}

    def _get(self, technology: str) -> AnchorCurve:
        try:
            return self._curves[technology]
        except KeyError:
            available = ", ".join(self.technologies())
            raise KeyError(
                f"unknown technology {technology!r}; available: {available}"
            ) from None
