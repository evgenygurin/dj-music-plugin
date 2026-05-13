"""Helpers for golden snapshot tests in tests/domain/transition.

A *golden test* re-runs current code against a frozen JSON snapshot of
expected output. Used as a behaviour guard during the v1.5.0 transition
architecture refactor.

Workflow:
  1. First run with REGEN_GOLDEN=1 writes <name>.json snapshots.
  2. Subsequent runs read snapshot, compare with current output at the
     declared tolerance.
  3. When a deliberate behaviour change happens, regenerate with
     REGEN_GOLDEN=1 in a dedicated commit reviewed in isolation.

Tolerance defaults are tight (1e-9 for component scores, 1e-7 for
overall, exact for booleans/strings). See callers for overrides.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).parent / "_golden"
REGEN = os.environ.get("REGEN_GOLDEN") == "1"


def _round(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "__nan__"
        if math.isinf(value):
            return "__inf__" if value > 0 else "__-inf__"
    return value


def _normalise(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalise(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_normalise(x) for x in obj]
    return _round(obj)


def load_or_write(name: str, actual: Any) -> Any:
    """Return expected snapshot, writing it on first run / under REGEN."""
    path = GOLDEN_DIR / f"{name}.json"
    payload = _normalise(actual)
    if REGEN or not path.exists():
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return payload
    return json.loads(path.read_text())


def assert_close(actual: float, expected: float | str, *, tol: float, label: str) -> None:
    """Numeric-aware comparison with explicit failure message."""
    if isinstance(actual, float) and math.isnan(actual) and expected == "__nan__":
        return
    if isinstance(expected, str):
        raise AssertionError(f"{label}: expected sentinel {expected!r} but actual is {actual!r}")
    delta = abs(actual - expected)
    assert delta <= tol, (
        f"{label}: actual={actual!r} expected={expected!r} delta={delta:.2e} tol={tol:.0e}"
    )


def assert_recipe_equal(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Per-keyframe + per-fx-event compare for NeuralMixRecipe.to_dict()."""
    for key in ("transition", "bars", "confidence", "rescue", "explanation"):
        assert actual.get(key) == expected.get(key), (
            f"recipe.{key} mismatch: actual={actual.get(key)!r} expected={expected.get(key)!r}"
        )
    assert actual.get("mix_in_section") == expected.get("mix_in_section")
    assert actual.get("mix_out_section") == expected.get("mix_out_section")
    a_kfs = actual["keyframes"]
    e_kfs = expected["keyframes"]
    assert len(a_kfs) == len(e_kfs), f"keyframe count {len(a_kfs)} vs {len(e_kfs)}"
    for i, (a, e) in enumerate(zip(a_kfs, e_kfs, strict=True)):
        assert a["deck"] == e["deck"], f"kf[{i}].deck"
        assert a["stem"] == e["stem"], f"kf[{i}].stem"
        assert_close(float(a["bar"]), float(e["bar"]), tol=1e-9, label=f"kf[{i}].bar")
        assert_close(
            float(a["level_db"]), float(e["level_db"]), tol=1e-9, label=f"kf[{i}].level_db"
        )
    a_fx = actual["fx_events"]
    e_fx = expected["fx_events"]
    assert len(a_fx) == len(e_fx), f"fx count {len(a_fx)} vs {len(e_fx)}"
    for i, (a, e) in enumerate(zip(a_fx, e_fx, strict=True)):
        assert a["deck"] == e["deck"]
        assert a["stem"] == e["stem"]
        assert a["trigger"] == e["trigger"]
        assert_close(float(a["bar"]), float(e["bar"]), tol=1e-9, label=f"fx[{i}].bar")
