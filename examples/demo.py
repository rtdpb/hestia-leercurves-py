"""Small demo: print learning-curve cost factors for a few technologies.

Run from the project root:

    python examples/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the demo runnable straight from a fresh clone ("python examples/demo.py")
# without needing `pip install` first, by putting the package's src/ on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hestia_leercurves import CurveSettings, LearningCurveModel  # noqa: E402

DATA_CSV = Path(__file__).resolve().parents[1] / "data" / "leercurves.csv"


def main() -> None:
    years = [2020, 2030, 2040, 2050]
    technologies = ["hWP", "eWPlw", "Warmtenet", "Isolatie", "Waterstof"]

    for label, settings in (
        ("default (blend 0.5, learning on)", CurveSettings()),
        ("optimistic (blend 0.0)", CurveSettings(min_max_shift=0.0)),
        ("learning off", CurveSettings(learning_shift=0.0)),
    ):
        model = LearningCurveModel.from_csv(DATA_CSV, settings)
        print(f"\n== {label} ==")
        header = "technology".ljust(12) + "".join(str(y).rjust(9) for y in years)
        print(header)
        for tech in technologies:
            row = tech.ljust(12) + "".join(
                f"{model.factor(tech, y):9.3f}" for y in years
            )
            print(row)


if __name__ == "__main__":
    main()
