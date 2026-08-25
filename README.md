# Hestia leercurves — GeoDMS → Python

A small, self-contained port of one module of the **Hestia** model (PBL/TNO)
from **GeoDMS** to clean, typed, tested **Python**.

Hestia simulates the heat transition of the Dutch built environment: for every
dwelling it computes energy use, and the costs and benefits of making it more
sustainable, for every year from 2000 to 2050. Part of that computation is the
**learning curve** (*leercurve*): the relative cost development of each
technology (heat pumps, heat networks, insulation, ...) over time.

This repository is a **faithful reimplementation** of that piece, based on the
public GeoDMS source. It is meant as a worked example of the kind of migration
the Hestia team is doing — *"het model omzetten van programmeertaal GeoDMS naar
Python"* — with an emphasis on readability and maintainability.

> Scope note: this reimplements one module of a large model, using only the
> public parameter data and source in the
> [public Hestia repository](https://github.com/pbl-nl/model-hestia-public).
> It is an independent study project, not affiliated with PBL or TNO.
> **Numerical equivalence against a running GeoDMS reference model has not yet
> been established** — see "Assumptions worth verifying" below.

## What the module does

For a technology and a view year ("zichtjaar") it returns a **cost factor**,
where `1.0` = 100% of that technology's base cost. Most technologies are indexed
to a **2020** reference (factor 100 in 2020); in Hestia 1.2 insulation
(`Isolatie`) and ventilation (`Ventilatie`) were reindexed around **2023**, so
their 100% point sits near 2023 rather than 2020. The factor is computed by:

1. **Interpolating** the optimistic and pessimistic cost curves linearly between
   the anchor years 2000, 2010, ... 2050 (constant outside that range).
2. **Blending** the two scenarios with a *min/max shift*
   (`0.0` = optimistic, `1.0` = pessimistic).
3. **Damping** with a *learning shift* (`0.0` = costs stay constant at 100%,
   `1.0` = the full curve is applied).

## The GeoDMS source, and its Python reimplementation

The original logic lives in two places in the public repo:

* the **anchor data** — `model/Kengetallen/Leercurves.dms`
  (`Optimistisch` / `Pessimistisch` factors per technology, per period);
* the **calculation** — the `MaakCurve` template in
  `model/stam/CalculationSchemes.dms` (lines 104–114).

The GeoDMS template:

```cpp
// template om leercurve te bepalen zoals die geldig is in een specifiek zichtjaar
template MaakCurve
{
    attribute<percent> Datamin (Classifications/Periode);   // optimistic anchors
    attribute<percent> DataMax (Classifications/Periode);   // pessimistic anchors

    parameter<ratio> CurveMin := interpolate_linear(Zichtjaar_jaar, Periode/EindJaar, DataMin) / 100[percent];
    parameter<ratio> CurveMax := interpolate_linear(Zichtjaar_jaar, Periode/EindJaar, DataMax) / 100[percent];
    parameter<ratio> Base     := CurveMin * Schuiven/CurveMin + CurveMax * Schuiven/CurveMax;
    parameter<ratio> Curve    := Base * Schuiven/LerenAan + 1[ratio] * Schuiven/LerenUit;
}
```

The Python reimplementation (`src/hestia_leercurves/model.py`, method `factor`):

```python
optimistic  = interpolate_linear(year, curve.years, curve.optimistic) / 100.0
pessimistic = interpolate_linear(year, curve.years, curve.pessimistic) / 100.0

shift = self.settings.min_max_shift            # Schuiven/CurveMax
base  = optimistic * (1.0 - shift) + pessimistic * shift

learning = self.settings.learning_shift        # Schuiven/LerenAan
return base * learning + 1.0 * (1.0 - learning)
```

### Translation decisions

| GeoDMS concept | Python choice | Why |
|---|---|---|
| `container` of `attribute`s over a `Periode` unit | `AnchorCurve` dataclass with `years`/`optimistic`/`pessimistic` tuples | Explicit, immutable, self-validating data. |
| `template MaakCurve` (per-item instantiation) | `LearningCurveModel.factor()` method | Behaviour lives in one place; instances are cheap to reuse. |
| `Schuiven` parameters from `DefaultSettings/Basis.dms` | `CurveSettings` dataclass, defaults loaded from `default_settings.toml` | Config, not code: the shift values live in a TOML file (like GeoDMS' settings layer), validated to `[0, 1]`. Override with `CurveSettings.from_toml(...)`. |
| `interpolate_linear` (clamps outside range) | `interpolation.interpolate_linear` | Reimplemented to match the public source, incl. constant extrapolation. |
| implicit `Default` references (`EWV := Default`) | resolved once into `data/leercurves.csv` | Keeps the runtime model simple; data stays declarative. |

### Assumptions worth verifying against the closed model

* **Numerical equivalence:** the expected values in the tests are derived from
  the published `MaakCurve` formula, not from a running GeoDMS model. End-to-end
  numerical equivalence against a running GeoDMS reference run still needs to be
  established.
* **Extrapolation:** GeoDMS `interpolate_linear` is assumed to clamp to the
  nearest endpoint outside `[2000, 2050]`. This is reimplemented here and covered
  by tests; it should be confirmed against the running GeoDMS model.
* **Data superset:** `Leercurves.dms` defines more technologies than the
  18-item `Classifications/LeerCurves` list actually iterated in the model. All
  of them are included here; the same formula applies regardless.

## Usage

```python
from hestia_leercurves import LearningCurveModel, CurveSettings

model = LearningCurveModel.from_csv("data/leercurves.csv")
model.factor("hWP", 2035)                 # 0.8575  (hybrid heat pump, default blend)
model.factors("Warmtenet", [2030, 2050])  # {2030: 1.0, 2050: 0.99}

optimistic = LearningCurveModel.from_csv("data/leercurves.csv",
                                         CurveSettings(min_max_shift=0.0))
optimistic.factor("Waterstof", 2050)      # 0.48
```

### Settings as config, not code

The default shift values are not hard-coded in Python; they live in
`src/hestia_leercurves/default_settings.toml` (the single source of truth,
mirroring the GeoDMS `DefaultSettings/Basis.dms` layer):

```toml
[curve]
min_max_shift  = 0.5   # 0 = optimistic, 1 = pessimistic
learning_shift = 1.0   # 0 = costs constant, 1 = full learning curve
```

Point at your own file to change a scenario without touching code:

```python
settings = CurveSettings.from_toml("my-settings.toml")   # missing keys fall back to defaults
model = LearningCurveModel.from_csv("data/leercurves.csv", settings)
```

Run the demo:

```bash
python examples/demo.py
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest   # 27 tests
ruff check .       # lint
```

The test suite pins the reimplementation to **hand-computed values** derived
from the published GeoDMS `MaakCurve` formula (e.g. `hWP` in 2035 → `0.8575`),
so it checks the port against that formula rather than just internal
consistency. This is not the same as numerical equivalence against a running
GeoDMS model, which still needs to be established.

## Layout

```
src/hestia_leercurves/
    interpolation.py   # clamped piecewise-linear interpolation
    model.py           # AnchorCurve, CurveSettings, Scenario, LearningCurveModel
data/leercurves.csv    # anchor data extracted from Leercurves.dms
examples/demo.py       # prints factors for a few technologies
tests/                 # pytest suite, expected values computed by hand
```

## License

GPL-3.0-or-later, matching the upstream Hestia model.
