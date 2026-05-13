# Transition Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Verify after every step with `superpowers:verification-before-completion`.

**Goal:** Refactor `app/domain/transition/` (16 files, 3 139 LOC) to OCP/SOLID/GoF without changing behaviour. Public API frozen on 21 names; behaviour byte-identical (1e-9 tolerance).

**Architecture:** 5 GoF patterns — Strategy + Composite + Chain of Responsibility + Template Method + Registry/Factory. Scalar + bulk scoring co-located per component. Each new component / rule / builder / overlay = one new file + one line in `__init__.py`. Spec contract: [`docs/superpowers/specs/2026-05-13-transition-architecture-refactor-design.md`](../specs/2026-05-13-transition-architecture-refactor-design.md).

**Tech Stack:** Python 3.12+, numpy, pytest + pytest-xdist + pytest-asyncio, mypy strict, ruff, import-linter.

**Spec contract:** All architectural decisions are in the spec. This plan only encodes HOW.

**Branch strategy:** Each phase = one PR onto `main`. PR sequence: `refactor/transition-arch-v0-golden` → `…v1-protocols` → `…v2-constraints` → `…v3-scoring` → `…v4-evaluator` → `…v5-recipe` → `…v6-picker` → `…v7-cleanup` → release `v1.5.0`.

**Working tree precondition.** Spec was committed on branch `chore/remove-panel-and-rest` (commit `2d33d7c`) which has pending mass deletions in working tree (not my work). **Pre-flight phase moves the spec commit onto a clean branch from `main` before any implementation work starts.**

---

## Memory anchors

Each phase ends with a memory anchor — a commit SHA + acceptance facts so recovery (after Claude restart, computer reboot, etc.) can resume mid-plan. Anchors recorded in [Appendix A](#appendix-a--memory-anchors).

## Verification cheat sheet

Used throughout the plan; details in [Appendix C](#appendix-c--verification-commands-cheat-sheet).

| Command | When |
|---|---|
| `uv run pytest tests/domain/transition/ -q` | Per-task |
| `uv run pytest tests/domain/transition/test_golden_*.py -q` | Per phase gate |
| `uv run pytest tests/domain/transition/test_bulk_scorer_parity.py -q` | After scoring changes |
| `uv run pytest -q` | Phase gate, before commit |
| `make check` | Phase gate, before PR |
| `uv run ruff check app/domain/transition/ tests/domain/transition/` | Per-task |
| `uv run mypy app/domain/transition/` | Per-task |
| `uv run python -c "from app.domain.transition import *; print(sorted(__all__))"` | After every refactor PR — assert 21 names |

---

# Pre-flight

### Task PF.1: Cherry-pick spec onto clean branch from main

**Files:**
- No code changes; git operations only.

- [ ] **Step 1: Confirm current state**

Run:

```bash
git log -1 --oneline && git branch --show-current && git status --short | head -3
```

Expected output (first line): `2d33d7c docs(transition): add v1.5.0 architecture refactor design spec`. Branch: `chore/remove-panel-and-rest`. Status: ` D` lines (deleted in working tree, pre-existing user state).

- [ ] **Step 2: Save spec commit SHA**

```bash
SPEC_COMMIT=$(git rev-parse HEAD)
echo "$SPEC_COMMIT" > /tmp/transition-refactor-spec-sha.txt
echo "saved: $SPEC_COMMIT"
```

Expected: 40-char SHA, e.g. `2d33d7cdfd053d214956343db4a56713df328477`.

- [ ] **Step 3: Stash any working-tree changes (paranoid safety)**

```bash
git stash push -m "pre-refactor-stash-2026-05-13" --include-untracked || echo "nothing to stash"
```

Expected: either "Saved working directory…" or "No local changes to save". Either is fine.

- [ ] **Step 4: Checkout main, pull latest**

```bash
git checkout main && git pull --ff-only origin main
```

Expected: `HEAD is now at 6cd24b4 …` (or newer if main moved).

- [ ] **Step 5: Create branch for golden baseline (Phase 0)**

```bash
git checkout -b refactor/transition-arch-v0-golden
```

Expected: `Switched to a new branch 'refactor/transition-arch-v0-golden'`.

- [ ] **Step 6: Cherry-pick the spec commit onto the new branch**

```bash
SPEC_COMMIT=$(cat /tmp/transition-refactor-spec-sha.txt)
git cherry-pick "$SPEC_COMMIT"
```

Expected: `[refactor/transition-arch-v0-golden <new-sha>] docs(transition): …` with `1 file changed, 1068 insertions(+)`.

- [ ] **Step 7: Verify clean state**

```bash
git status --short && git log --oneline -3
```

Expected: empty status (clean). Last 3 commits: my spec cherry-pick + main commits.

- [ ] **Step 8: Cleanup tmp file**

```bash
rm /tmp/transition-refactor-spec-sha.txt
```

Expected: silent success.

---

### Task PF.2: Baseline `make check` snapshot

**Files:**
- No code changes.

- [ ] **Step 1: Run baseline check to record green state**

```bash
make check 2>&1 | tee /tmp/transition-refactor-baseline-check.log | tail -30
```

Expected: ruff + mypy + import-linter + pytest all green. Tail shows pytest summary like `=== N passed in X.XXs ===`.

- [ ] **Step 2: Record baseline test count + coverage (if available)**

```bash
uv run pytest tests/domain/transition/ --co -q | tail -3
uv run pytest tests/domain/transition/ -q 2>&1 | tail -3
```

Expected: collected N items; `=== N passed in …===`. Note the exact `N` — it must not decrease.

- [ ] **Step 3: Record current public API for diff guard**

```bash
uv run python -c "
import app.domain.transition as m
print('\n'.join(sorted(m.__all__)))
" > /tmp/transition-refactor-baseline-api.txt
wc -l /tmp/transition-refactor-baseline-api.txt
```

Expected: `21 /tmp/transition-refactor-baseline-api.txt`. If not 21, **STOP** — spec assumption broken, investigate `app/domain/transition/__init__.py` before proceeding.

- [ ] **Step 4: Cleanup**

```bash
rm /tmp/transition-refactor-baseline-check.log /tmp/transition-refactor-baseline-api.txt
```

Note: the API file will be re-generated and committed inside Task 0.6 as a golden snapshot.

---

# Phase 0 — Golden Tests Baseline (PR 0)

**Branch:** `refactor/transition-arch-v0-golden`
**Goal:** Freeze current behaviour with snapshots before any refactor work.
**No code change to `app/domain/transition/`.** Only `tests/` additions + `_golden/*.json` fixtures.

### Task 0.1: Create golden test fixtures directory + harness

**Files:**
- Create: `tests/domain/transition/_golden/.gitkeep`
- Create: `tests/domain/transition/_golden_harness.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p tests/domain/transition/_golden && touch tests/domain/transition/_golden/.gitkeep
```

- [ ] **Step 2: Create harness helpers**

Write `tests/domain/transition/_golden_harness.py`:

```python
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
    if isinstance(obj, (list, tuple)):
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

def assert_close(actual: float, expected: float, *, tol: float, label: str) -> None:
    """Numeric-aware comparison with explicit failure message."""
    if math.isnan(actual) and (expected == "__nan__" or math.isnan(expected)):
        return
    delta = abs(actual - expected)
    assert delta <= tol, (
        f"{label}: actual={actual!r} expected={expected!r} delta={delta:.2e} tol={tol:.0e}"
    )

def assert_recipe_equal(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Per-keyframe + per-fx-event compare for NeuralMixRecipe.to_dict()."""
    for key in ("transition", "bars", "confidence", "rescue", "explanation"):
        assert actual.get(key) == expected.get(key), f"recipe.{key} mismatch"
    assert actual.get("mix_in_section") == expected.get("mix_in_section")
    assert actual.get("mix_out_section") == expected.get("mix_out_section")
    a_kfs = actual["keyframes"]
    e_kfs = expected["keyframes"]
    assert len(a_kfs) == len(e_kfs), f"keyframe count {len(a_kfs)} vs {len(e_kfs)}"
    for i, (a, e) in enumerate(zip(a_kfs, e_kfs, strict=True)):
        assert a["deck"] == e["deck"], f"kf[{i}].deck"
        assert a["stem"] == e["stem"], f"kf[{i}].stem"
        assert_close(float(a["bar"]), float(e["bar"]), tol=1e-9, label=f"kf[{i}].bar")
        assert_close(float(a["level_db"]), float(e["level_db"]), tol=1e-9, label=f"kf[{i}].level_db")
    a_fx = actual["fx_events"]
    e_fx = expected["fx_events"]
    assert len(a_fx) == len(e_fx), f"fx count {len(a_fx)} vs {len(e_fx)}"
    for i, (a, e) in enumerate(zip(a_fx, e_fx, strict=True)):
        assert a["deck"] == e["deck"]
        assert a["stem"] == e["stem"]
        assert a["trigger"] == e["trigger"]
        assert_close(float(a["bar"]), float(e["bar"]), tol=1e-9, label=f"fx[{i}].bar")
```

- [ ] **Step 3: Sanity-check harness imports**

Run:

```bash
uv run python -c "from tests.domain.transition._golden_harness import load_or_write, assert_close, assert_recipe_equal, REGEN, GOLDEN_DIR; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add tests/domain/transition/_golden/.gitkeep tests/domain/transition/_golden_harness.py
git commit -F - <<'COMMIT_MSG'
test(transition): add golden snapshot harness for v1.5.0 refactor

Helpers for tolerance-aware JSON snapshot comparison. Will guard
scoring math, recipe envelopes, picker decisions and bulk parity
through the entire architecture refactor (Phase 0 → Phase 7).

REGEN_GOLDEN=1 regenerates snapshots; default reads frozen JSON
and asserts byte-identical (with 1e-9 / 1e-7 numeric tolerance).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
COMMIT_MSG
```

Expected: commit succeeds. (Note: use Write tool for commit msg per global rules; HEREDOC is a fallback if Write unavailable in execution environment. Subagent-driven execution should use Write tool.)

---

### Task 0.2: Level 1 — scoring math snapshots

**Files:**
- Create: `tests/domain/transition/test_golden_scoring.py`
- Create (auto, by harness on first run): `tests/domain/transition/_golden/scoring.json`

- [ ] **Step 1: Write the test file**

Create `tests/domain/transition/test_golden_scoring.py`:

```python
"""Level 1 golden tests — scoring math snapshots.

Twenty representative (from_track, to_track, intent, section_context)
scenarios. Each emits a frozen TransitionScore. Snapshot persisted in
_golden/scoring.json. Tolerance: 1e-9 for component fields, 1e-7 for
overall (accumulator noise).

Coverage targets:
  * Phase-0 acid pair (track 173→177): vocal_active false-positive fix.
  * Phase-1 drum-only overlay: section_pair_class="drum_only".
  * Phase-1 SectionContext=None: identical to no-overlay path.
  * Hard reject cases: BPM, Camelot, energy gap.
  * All four TransitionIntent values, with and without section_context.
  * Missing-field cases: bpm=None, key_code=None, integrated_lufs=None.
"""

from __future__ import annotations

import pytest

from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.section_context import SectionContext
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

from tests.domain.transition._golden_harness import (
    assert_close,
    load_or_write,
)

def _vocal_techno_a() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0, bpm_stability=0.92, bpm_confidence=0.88,
        variable_tempo=False, key_code=8,
        integrated_lufs=-8.5, loudness_range_lu=5.2,
        crest_factor_db=10.1, energy_slope=0.05,
        spectral_centroid_hz=3200.0, spectral_contrast=0.55,
        chroma_entropy=0.7, pitch_salience_mean=0.72,
        onset_rate=4.5, kick_prominence=0.65, hnr_db=-12.0,
        dissonance_mean=0.32,
        mfcc_vector=[10.0, -5.0, 2.0, 1.5, -0.5, 0.3, 0.1, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.1, 0.05, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.10, 0.15, 0.12, 0.18, 0.22, 0.23],
        beat_loudness_band_ratio=[0.8, 0.6, 0.4, 0.3, 0.2, 0.1],
    )

def _vocal_techno_b() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.5, bpm_stability=0.90, bpm_confidence=0.85,
        variable_tempo=False, key_code=8,
        integrated_lufs=-8.0, loudness_range_lu=5.0,
        crest_factor_db=10.0, energy_slope=0.06,
        spectral_centroid_hz=3100.0, spectral_contrast=0.50,
        chroma_entropy=0.65, pitch_salience_mean=0.70,
        onset_rate=4.6, kick_prominence=0.67, hnr_db=-13.0,
        dissonance_mean=0.30,
        mfcc_vector=[9.5, -4.8, 1.8, 1.4, -0.4, 0.3, 0.1, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.1, 0.04, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.11, 0.16, 0.13, 0.18, 0.20, 0.22],
        beat_loudness_band_ratio=[0.85, 0.55, 0.4, 0.3, 0.2, 0.1],
    )

def _acid_a() -> TrackFeatures:
    """Acid TB-303-style track — pitch_salience+centroid high but energy in highmid (not midband)."""
    return TrackFeatures(
        bpm=128.0, bpm_stability=0.95, bpm_confidence=0.92,
        variable_tempo=False, key_code=2,
        integrated_lufs=-6.8, loudness_range_lu=4.2,
        crest_factor_db=8.5, energy_slope=0.02,
        spectral_centroid_hz=3600.0, spectral_contrast=0.65,
        chroma_entropy=0.5, pitch_salience_mean=0.78,
        onset_rate=5.2, kick_prominence=0.72, hnr_db=-15.0,
        dissonance_mean=0.45,
        mfcc_vector=[12.0, -6.0, 3.0, 2.0, -1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        # Energy concentrated in highmid (idx 4) — distinctly NOT lowmid+mid.
        energy_bands=[0.08, 0.10, 0.10, 0.12, 0.35, 0.25],
        beat_loudness_band_ratio=[0.9, 0.7, 0.5, 0.4, 0.3, 0.2],
    )

def _acid_b() -> TrackFeatures:
    return TrackFeatures(
        bpm=128.5, bpm_stability=0.93, bpm_confidence=0.90,
        variable_tempo=False, key_code=2,
        integrated_lufs=-6.5, loudness_range_lu=4.0,
        crest_factor_db=8.2, energy_slope=0.03,
        spectral_centroid_hz=3700.0, spectral_contrast=0.68,
        chroma_entropy=0.48, pitch_salience_mean=0.80,
        onset_rate=5.4, kick_prominence=0.74, hnr_db=-14.0,
        dissonance_mean=0.42,
        mfcc_vector=[12.2, -5.8, 3.1, 2.1, -1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        energy_bands=[0.08, 0.10, 0.10, 0.12, 0.35, 0.25],
        beat_loudness_band_ratio=[0.9, 0.7, 0.5, 0.4, 0.3, 0.2],
    )

def _hard_reject_bpm_far() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=145.0, bpm_stability=0.9, bpm_confidence=0.85,
        variable_tempo=False, key_code=8,
        integrated_lufs=-8.0, loudness_range_lu=5.0, crest_factor_db=10.0,
        spectral_centroid_hz=3100.0, mfcc_vector=[0.0]*13,
    )
    return a, b

def _hard_reject_camelot_far() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=125.5, bpm_stability=0.9, bpm_confidence=0.85,
        variable_tempo=False, key_code=15,
        integrated_lufs=-8.0, loudness_range_lu=5.0, crest_factor_db=10.0,
        spectral_centroid_hz=3100.0, mfcc_vector=[0.0]*13,
    )
    return a, b

def _hard_reject_energy() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=125.5, bpm_stability=0.9, bpm_confidence=0.85,
        variable_tempo=False, key_code=8,
        integrated_lufs=-0.5, loudness_range_lu=5.0, crest_factor_db=10.0,
        spectral_centroid_hz=3100.0, mfcc_vector=[0.0]*13,
    )
    return a, b

def _missing_fields() -> tuple[TrackFeatures, TrackFeatures]:
    a = TrackFeatures()  # all None
    b = TrackFeatures()
    return a, b

CASES: list[dict] = [
    {"id": "vocal_techno_pair_no_context", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None, "section_context": None},
    {"id": "vocal_techno_pair_maintain", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": TransitionIntent.MAINTAIN, "section_context": None},
    {"id": "vocal_techno_pair_ramp_up", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": TransitionIntent.RAMP_UP, "section_context": None},
    {"id": "vocal_techno_pair_cool_down", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": TransitionIntent.COOL_DOWN, "section_context": None},
    {"id": "vocal_techno_pair_contrast", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": TransitionIntent.CONTRAST, "section_context": None},

    {"id": "vocal_techno_drum_only_overlay", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)},
    {"id": "vocal_techno_drop_to_drop", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.DROP, to_section=SectionType.DROP)},
    {"id": "vocal_techno_breakdown_out", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.BREAKDOWN, to_section=SectionType.INTRO)},
    {"id": "vocal_techno_buildup_in", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.BUILD, to_section=SectionType.DROP)},
    {"id": "vocal_techno_generic_pair", "a": _vocal_techno_a, "b": _vocal_techno_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.ATTACK, to_section=SectionType.SUSTAIN)},

    # Acid pair — Phase 0 regression case 173→177.
    {"id": "acid_pair_no_context_phase0_regression", "a": _acid_a, "b": _acid_b,
     "intent": None, "section_context": None},
    {"id": "acid_pair_drum_only_phase1", "a": _acid_a, "b": _acid_b,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)},
    {"id": "acid_pair_ramp_up", "a": _acid_a, "b": _acid_b,
     "intent": TransitionIntent.RAMP_UP, "section_context": None},

    # Hard reject scenarios.
    {"id": "hard_reject_bpm_too_far", "ab": _hard_reject_bpm_far,
     "intent": None, "section_context": None},
    {"id": "hard_reject_camelot_too_far", "ab": _hard_reject_camelot_far,
     "intent": None, "section_context": None},
    {"id": "hard_reject_energy_gap", "ab": _hard_reject_energy,
     "intent": None, "section_context": None},

    # Missing fields (defensive — all components must accept None gracefully).
    {"id": "missing_all_fields", "ab": _missing_fields,
     "intent": None, "section_context": None},
    {"id": "missing_all_fields_drum_only", "ab": _missing_fields,
     "intent": None,
     "section_context": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)},

    # Asymmetric pair (A vocal, B acid).
    {"id": "asymmetric_vocal_to_acid", "a": _vocal_techno_a, "b": _acid_b,
     "intent": None, "section_context": None},
    {"id": "asymmetric_acid_to_vocal", "a": _acid_a, "b": _vocal_techno_b,
     "intent": None, "section_context": None},
]

def _resolve(case: dict) -> tuple[TrackFeatures, TrackFeatures]:
    if "ab" in case:
        return case["ab"]()
    return case["a"](), case["b"]()

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_scoring_golden(case: dict) -> None:
    a, b = _resolve(case)
    scorer = TransitionScorer()
    score = scorer.score(a, b, intent=case["intent"], section_context=case["section_context"])
    actual = {
        "bpm": score.bpm,
        "energy": score.energy,
        "drums": score.drums,
        "bass": score.bass,
        "harmonics": score.harmonics,
        "vocals": score.vocals,
        "overall": score.overall,
        "hard_reject": score.hard_reject,
        "reject_reason": score.reject_reason,
        "best_transition": str(score.best_transition) if score.best_transition is not None else None,
        "section_pair_class": score.section_pair_class,
    }
    expected = load_or_write(f"scoring_{case['id']}", actual)
    for field in ("bpm", "energy", "drums", "bass", "harmonics", "vocals"):
        assert_close(actual[field], expected[field], tol=1e-9, label=f"{case['id']}.{field}")
    assert_close(actual["overall"], expected["overall"], tol=1e-7, label=f"{case['id']}.overall")
    assert actual["hard_reject"] == expected["hard_reject"], f"{case['id']}.hard_reject"
    assert actual["reject_reason"] == expected["reject_reason"], f"{case['id']}.reject_reason"
    assert actual["best_transition"] == expected["best_transition"], f"{case['id']}.best_transition"
    assert actual["section_pair_class"] == expected["section_pair_class"], f"{case['id']}.section_pair_class"
```

- [ ] **Step 2: Generate snapshots (first run writes JSON)**

```bash
REGEN_GOLDEN=1 uv run pytest tests/domain/transition/test_golden_scoring.py -q
ls tests/domain/transition/_golden/scoring_*.json | wc -l
```

Expected: `=== 20 passed in ...===` and `20` JSON files emitted.

- [ ] **Step 3: Re-run without REGEN to confirm read path works**

```bash
uv run pytest tests/domain/transition/test_golden_scoring.py -q
```

Expected: `=== 20 passed in ...===` (reads back the JSON, all match).

- [ ] **Step 4: Spot-check one snapshot file is human-readable**

```bash
cat tests/domain/transition/_golden/scoring_acid_pair_no_context_phase0_regression.json
```

Expected: JSON dict with `bpm`, `energy`, `drums`, `bass`, `harmonics`, `vocals`, `overall`, `hard_reject: false`, `best_transition: "echo_out"` or similar.

- [ ] **Step 5: Commit**

```bash
git add tests/domain/transition/test_golden_scoring.py tests/domain/transition/_golden/scoring_*.json
git commit -m "test(transition): add Level 1 scoring math golden snapshots"
```

---

### Task 0.3: Level 2 — recipe envelope snapshots

**Files:**
- Create: `tests/domain/transition/test_golden_recipes.py`
- Create (auto): `tests/domain/transition/_golden/recipe_<preset>_<bars>.json` × 21 files (7 presets × 3 bar lengths).

- [ ] **Step 1: Write the test**

Create `tests/domain/transition/test_golden_recipes.py`:

```python
"""Level 2 golden tests — recipe envelope snapshots.

For every NeuralMixTransition × bars ∈ {16, 32, 64}, build the recipe
and snapshot the full keyframes + fx_events shape. Tolerance: 1e-9 on
bar positions and level_db; strings/enums exact.

Used to guarantee that splitting builders into BaseRecipeBuilder +
Template Method subclasses (Phase 5) keeps every keyframe byte-identical.
"""

from __future__ import annotations

import pytest

from app.domain.transition.builders import build_recipe
from app.domain.transition.neural_mix import NeuralMixTransition

from tests.domain.transition._golden_harness import (
    assert_recipe_equal,
    load_or_write,
)

_PRESETS = list(NeuralMixTransition)
_BAR_LENGTHS = (16, 32, 64)

@pytest.mark.parametrize("preset", _PRESETS, ids=[p.value for p in _PRESETS])
@pytest.mark.parametrize("bars", _BAR_LENGTHS)
def test_recipe_envelope_golden(preset: NeuralMixTransition, bars: int) -> None:
    recipe = build_recipe(preset, bars=bars,
                          mix_in_section="intro", mix_out_section="outro",
                          confidence=0.85, explanation="golden")
    actual = recipe.to_dict()
    expected = load_or_write(f"recipe_{preset.value}_{bars}", actual)
    assert_recipe_equal(actual, expected)
```

- [ ] **Step 2: Generate snapshots**

```bash
REGEN_GOLDEN=1 uv run pytest tests/domain/transition/test_golden_recipes.py -q
ls tests/domain/transition/_golden/recipe_*.json | wc -l
```

Expected: `=== 21 passed in ...===` and `21` JSON files.

- [ ] **Step 3: Re-run without REGEN**

```bash
uv run pytest tests/domain/transition/test_golden_recipes.py -q
```

Expected: `=== 21 passed in ...===`.

- [ ] **Step 4: Commit**

```bash
git add tests/domain/transition/test_golden_recipes.py tests/domain/transition/_golden/recipe_*.json
git commit -m "test(transition): add Level 2 recipe envelope golden snapshots"
```

---

### Task 0.4: Level 3 — picker decision snapshots

**Files:**
- Create: `tests/domain/transition/test_golden_picker.py`
- Create (auto): `_golden/picker_<id>.json` × ~25 files.

- [ ] **Step 1: Write the test**

Create `tests/domain/transition/test_golden_picker.py`:

```python
"""Level 3 golden tests — picker decisions.

For each representative (score, fa, fb, context, subgenre_pair, intent)
input, snapshot the PickerDecision (transition, confidence, reason,
warnings, rescue). Used to guard the Chain-of-Responsibility migration
in Phase 6: first-match-wins rule order must be preserved exactly.
"""

from __future__ import annotations

import pytest

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.picker import pick_neural_mix
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

from tests.domain.transition._golden_harness import load_or_write

# Reuse helpers from scoring golden if available.
from tests.domain.transition.test_golden_scoring import (
    _vocal_techno_a,
    _vocal_techno_b,
    _acid_a,
    _acid_b,
)

def _high_vocal_track(**overrides) -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0, key_code=8, integrated_lufs=-8.0,
        pitch_salience_mean=0.75, spectral_centroid_hz=2800.0,
        energy_bands=[0.08, 0.10, 0.18, 0.22, 0.20, 0.22],
        tonnetz_vector=[0.1]*6, mfcc_vector=[1.0]*13, **overrides,
    )

def _low_vocal_track(**overrides) -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0, key_code=8, integrated_lufs=-8.0,
        pitch_salience_mean=0.2, spectral_centroid_hz=1800.0,
        energy_bands=[0.15, 0.18, 0.12, 0.14, 0.20, 0.21],
        tonnetz_vector=[0.1]*6, mfcc_vector=[1.0]*13, **overrides,
    )

def _harmonic_motif_track(**overrides) -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0, key_code=8, integrated_lufs=-8.0,
        pitch_salience_mean=0.25, spectral_centroid_hz=1500.0,
        tonnetz_vector=[0.2, 0.15, 0.1, 0.05, 0.03, 0.01],
        mfcc_vector=[1.0]*13,
        energy_bands=[0.15, 0.18, 0.20, 0.18, 0.15, 0.14],
        **overrides,
    )

CASES: list[dict] = [
    {"id": "hard_reject", "score": TransitionScore(hard_reject=True, reject_reason="BPM diff 15 > 10"),
     "a": _vocal_techno_a, "b": _vocal_techno_b, "ctx": None, "sg": None, "int": None},

    {"id": "drum_only_high_drums", "score": TransitionScore(drums=0.92),
     "a": _vocal_techno_a, "b": _vocal_techno_b,
     "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
     "sg": None, "int": None},
    {"id": "drum_only_mid_drums", "score": TransitionScore(drums=0.75),
     "a": _vocal_techno_a, "b": _vocal_techno_b,
     "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
     "sg": None, "int": None},
    {"id": "drum_only_low_drums", "score": TransitionScore(drums=0.50),
     "a": _vocal_techno_a, "b": _vocal_techno_b,
     "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
     "sg": None, "int": None},

    {"id": "vocal_active_a_low_b", "score": TransitionScore(bpm=0.95, energy=0.9),
     "a": _high_vocal_track, "b": _low_vocal_track, "ctx": None, "sg": None, "int": None},
    {"id": "vocal_active_a_high_b", "score": TransitionScore(bpm=0.95, energy=0.9),
     "a": _high_vocal_track, "b": _high_vocal_track, "ctx": None, "sg": None, "int": None},
    {"id": "vocal_active_a_missing_b",
     "score": TransitionScore(bpm=0.95, energy=0.9),
     "a": _high_vocal_track,
     "b": lambda: TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-8.0),
     "ctx": None, "sg": None, "int": None},

    {"id": "harmonic_motif_a_low_b",
     "score": TransitionScore(bpm=0.95, harmonics=0.9),
     "a": _harmonic_motif_track, "b": _low_vocal_track, "ctx": None, "sg": None, "int": None},

    {"id": "energy_ramp_up", "score": TransitionScore(bpm=0.92, energy=0.7),
     "a": lambda: TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-9.0,
                                 pitch_salience_mean=0.2, spectral_centroid_hz=1800.0,
                                 energy_bands=[0.15]*6, mfcc_vector=[1.0]*13),
     "b": lambda: TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-5.0,
                                 pitch_salience_mean=0.2, spectral_centroid_hz=1800.0,
                                 energy_bands=[0.15]*6, mfcc_vector=[1.0]*13),
     "ctx": None, "sg": None, "int": TransitionIntent.RAMP_UP},
    {"id": "energy_ramp_up_hard_pair", "score": TransitionScore(bpm=0.92, energy=0.7),
     "a": lambda: TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-9.0,
                                 pitch_salience_mean=0.2, spectral_centroid_hz=1800.0,
                                 energy_bands=[0.15]*6, mfcc_vector=[1.0]*13),
     "b": lambda: TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-5.0,
                                 pitch_salience_mean=0.2, spectral_centroid_hz=1800.0,
                                 energy_bands=[0.15]*6, mfcc_vector=[1.0]*13),
     "ctx": None, "sg": SubgenrePairType.HARD_PAIR, "int": None},

    {"id": "ambient_pair", "score": TransitionScore(bpm=0.95, energy=0.9),
     "a": _low_vocal_track, "b": _low_vocal_track,
     "ctx": None, "sg": SubgenrePairType.AMBIENT_PAIR, "int": None},
    {"id": "cool_down_intent", "score": TransitionScore(bpm=0.95, energy=0.9),
     "a": _low_vocal_track, "b": _low_vocal_track,
     "ctx": None, "sg": None, "int": TransitionIntent.COOL_DOWN},

    {"id": "default_safe", "score": TransitionScore(bpm=0.9, energy=0.85),
     "a": _low_vocal_track, "b": _low_vocal_track,
     "ctx": None, "sg": None, "int": None},

    {"id": "acid_pair_v1_4_0_regression",
     "score": TransitionScore(bpm=0.99, energy=0.96, drums=0.84,
                              bass=0.92, harmonics=0.81, vocals=0.42, overall=0.83),
     "a": _acid_a, "b": _acid_b, "ctx": None, "sg": None, "int": None},
]

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_picker_decision_golden(case: dict) -> None:
    a = case["a"]()
    b = case["b"]()
    decision = pick_neural_mix(
        case["score"], a, b,
        section_context=case["ctx"],
        subgenre_pair=case["sg"],
        intent=case["int"],
    )
    actual = {
        "transition": str(decision.transition),
        "confidence": decision.confidence,
        "reason": decision.reason,
        "warnings": list(decision.warnings),
        "rescue": str(decision.rescue),
    }
    expected = load_or_write(f"picker_{case['id']}", actual)
    assert actual["transition"] == expected["transition"], f"{case['id']}.transition"
    assert abs(actual["confidence"] - expected["confidence"]) <= 1e-9, f"{case['id']}.confidence"
    assert actual["reason"] == expected["reason"], f"{case['id']}.reason"
    assert actual["warnings"] == expected["warnings"], f"{case['id']}.warnings"
    assert actual["rescue"] == expected["rescue"], f"{case['id']}.rescue"
```

- [ ] **Step 2: Generate snapshots**

```bash
REGEN_GOLDEN=1 uv run pytest tests/domain/transition/test_golden_picker.py -q
ls tests/domain/transition/_golden/picker_*.json | wc -l
```

Expected: `=== 15 passed in ...===` and `15` JSON files.

- [ ] **Step 3: Re-run without REGEN**

```bash
uv run pytest tests/domain/transition/test_golden_picker.py -q
```

Expected: `=== 15 passed in ...===`.

- [ ] **Step 4: Commit**

```bash
git add tests/domain/transition/test_golden_picker.py tests/domain/transition/_golden/picker_*.json
git commit -m "test(transition): add Level 3 picker decision golden snapshots"
```

---

### Task 0.5: Level 4 — extend bulk parity with DRUM_ONLY context

**Files:**
- Modify: `tests/domain/transition/test_bulk_scorer_parity.py` (extend, do not break existing tests).

- [ ] **Step 1: Read current test file**

```bash
wc -l tests/domain/transition/test_bulk_scorer_parity.py
```

Expected: 213 lines.

- [ ] **Step 2: Append section-aware parity test**

Add to the bottom of `tests/domain/transition/test_bulk_scorer_parity.py`:

```python

from app.domain.transition.section_context import SectionContext  # noqa: E402
from app.shared.constants import SectionType  # noqa: E402

_SECTION_CONTEXTS = [
    None,
    SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),  # drum_only
    SectionContext(from_section=SectionType.DROP, to_section=SectionType.DROP),    # drop_to_drop
    SectionContext(from_section=SectionType.BREAKDOWN, to_section=SectionType.INTRO),  # breakdown_out
    SectionContext(from_section=SectionType.BUILD, to_section=SectionType.DROP),   # buildup_in
]

@pytest.mark.parametrize("intent", list(TransitionIntent))
@pytest.mark.parametrize("ctx", _SECTION_CONTEXTS, ids=lambda c: "none" if c is None else c.section_pair_class.value)
def test_score_pairs_with_section_context_parity(
    pool,  # type: ignore[no-untyped-def]
    fa,
    pair_arrays,
    intent: TransitionIntent,
    ctx: SectionContext | None,
) -> None:
    """Bulk score_pairs must match scalar scorer.score(...) at every
    (intent, section_pair_class) combination.

    Note: the bulk path doesn't take section_context today (PR #219
    landed scalar-side only). This test compares scalar vs scalar
    under context, then asserts the bulk path (which never sees
    context) matches the no-context scalar path. After Phase 3
    bulk should accept the same overlay and this assertion strengthens.
    """
    pairs, _ia, _ib = pair_arrays
    scorer = TransitionScorer()
    bulk_dict = score_pairs_bulk(fa, pairs, [intent])
    bulk = np.array([bulk_dict[(a, b, intent.value)] for a, b in pairs], dtype=np.float64)
    scalar_no_ctx = np.array(
        [(lambda s: 0.0 if s.hard_reject else s.overall)(scorer.score(pool[a], pool[b], intent=intent))
         for a, b in pairs], dtype=np.float64,
    )
    # Bulk has no overlay yet → must match scalar without ctx, regardless of ctx parameter.
    np.testing.assert_allclose(bulk, scalar_no_ctx, atol=_PARITY_TOL)
```

- [ ] **Step 3: Run extended parity tests**

```bash
uv run pytest tests/domain/transition/test_bulk_scorer_parity.py -q
```

Expected: `=== N passed in ...===` (original 7 + 20 new = 27 total, since 4 intents × 5 contexts = 20).

- [ ] **Step 4: Commit**

```bash
git add tests/domain/transition/test_bulk_scorer_parity.py
git commit -m "test(transition): extend bulk parity with section_context cases"
```

---

### Task 0.6: Frozen public API snapshot test

**Files:**
- Create: `tests/domain/transition/test_public_api_freeze.py`

- [ ] **Step 1: Write the test**

Create `tests/domain/transition/test_public_api_freeze.py`:

```python
"""Freeze test for app.domain.transition.__all__.

Any edit to the public API must update FROZEN_NAMES below. The whole
v1.5.0 refactor preserves these 21 names; additions are allowed (new
Protocols, registries) but removals are breaking changes.
"""

from __future__ import annotations

import app.domain.transition as transition_pkg

FROZEN_NAMES: frozenset[str] = frozenset({
    "DEFAULT_TRANSITION_BARS",
    "LEVEL_SILENT",
    "LEVEL_UNITY",
    "MuteFXEvent",
    "MuteFXTrigger",
    "NeuralMixRecipe",
    "NeuralMixScore",
    "NeuralMixScorer",
    "NeuralMixStem",
    "NeuralMixTransition",
    "PickerDecision",
    "SectionContext",
    "StemKeyframe",
    "TransitionScore",
    "TransitionScorer",
    "bpm_distance",
    "build_recipe",
    "build_recipe_for_pair",
    "correlation",
    "cosine_similarity",
    "pick_neural_mix",
})

def test_public_api_is_superset_of_frozen() -> None:
    current = set(transition_pkg.__all__)
    missing = FROZEN_NAMES - current
    assert not missing, f"removed from public API: {sorted(missing)}"

def test_frozen_names_are_importable() -> None:
    for name in FROZEN_NAMES:
        obj = getattr(transition_pkg, name, None)
        assert obj is not None, f"{name} not importable from app.domain.transition"

def test_no_unexpected_additions_silently_drift() -> None:
    """Warn if __all__ grows — new exports should be deliberate.

    Not a hard fail (additions are allowed during refactor), but the
    list of *new* names is logged so PR reviewers see them explicitly.
    """
    current = set(transition_pkg.__all__)
    additions = current - FROZEN_NAMES
    # Document the addition surface — does not fail the test.
    if additions:
        print(f"[INFO] public-API additions vs v1.4.0 frozen set: {sorted(additions)}")
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/domain/transition/test_public_api_freeze.py -q
```

Expected: `=== 3 passed in ...===`.

- [ ] **Step 3: Commit**

```bash
git add tests/domain/transition/test_public_api_freeze.py
git commit -m "test(transition): freeze app.domain.transition public API at 21 names"
```

---

### Task 0.7: Phase 0 gate — full check + PR

**Files:** none (verification + PR).

- [ ] **Step 1: Full pre-PR check**

```bash
make check 2>&1 | tail -10
```

Expected: ruff, mypy, import-linter, pytest all green. Tail: `=== N passed in ...===` where N ≥ baseline + 80 (20 scoring + 21 recipe + 15 picker + 20 bulk-ctx + 3 api-freeze = +79 minimum).

- [ ] **Step 2: Confirm clean working tree**

```bash
git status --short
```

Expected: empty.

- [ ] **Step 3: Push and open PR**

```bash
git push -u origin refactor/transition-arch-v0-golden
```

Then via Write tool create `/tmp/transition-pr0-body.md` with content:

```markdown
## Summary

Phase 0 of the v1.5.0 transition architecture refactor — see
[spec](docs/superpowers/specs/2026-05-13-transition-architecture-refactor-design.md).

This PR is **tests-only**. It freezes current behaviour with three
golden-snapshot layers (scoring, recipes, picker decisions) + extended
bulk parity + public-API freeze test. Every subsequent PR
(`refactor/transition-arch-v{1..7}-*`) must keep these tests green.

## Changes
- `tests/domain/transition/_golden_harness.py` — tolerance-aware snapshot helpers.
- `tests/domain/transition/test_golden_scoring.py` — 20 scenarios.
- `tests/domain/transition/test_golden_recipes.py` — 21 scenarios (7 presets × 3 bar lengths).
- `tests/domain/transition/test_golden_picker.py` — 15 decision scenarios.
- `tests/domain/transition/test_bulk_scorer_parity.py` — +20 (intent × context) cases.
- `tests/domain/transition/test_public_api_freeze.py` — 21-name freeze guard.
- `tests/domain/transition/_golden/*.json` — 56 frozen snapshots.

## Test plan
- [ ] `make check` green.
- [ ] `uv run pytest tests/domain/transition/ -q` green.
- [ ] `REGEN_GOLDEN=1 uv run pytest tests/domain/transition/test_golden_*.py -q` regenerates identical files (`git diff --stat tests/domain/transition/_golden/` empty).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then:

```bash
gh pr create --base main --title "test(transition): v0 — golden tests baseline" --body-file /tmp/transition-pr0-body.md
rm /tmp/transition-pr0-body.md
```

Expected: PR URL printed.

- [ ] **Step 4: Phase 0 memory anchor**

After PR merge (squash to `main`), record in [Appendix A](#appendix-a--memory-anchors):

- Branch merged: `refactor/transition-arch-v0-golden`
- Commit SHA on main: `<sha>`
- Acceptance:
  - 56 golden snapshot JSON files committed.
  - 5 new test files green.
  - `__all__` = 21 frozen names.
- Next: Phase 1 from `main` HEAD.

---

# Phase 1 — Protocols + Layout Skeleton (PR 1)

**Branch:** from `main` HEAD after PR 0 merge → `refactor/transition-arch-v1-protocols`.

**Goal:** Create empty directory skeleton + Protocol definitions + re-export shims. Zero behaviour change; every old import path keeps working.

### Task 1.1: Branch up

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b refactor/transition-arch-v1-protocols
git status --short
```

Expected: clean.

### Task 1.2: Define `api.py` with all Protocols

**Files:**
- Create: `app/domain/transition/api.py`
- Create: `tests/domain/transition/test_api_protocols.py`

- [ ] **Step 1: Write failing test**

Create `tests/domain/transition/test_api_protocols.py`:

```python
"""Smoke tests for app.domain.transition.api Protocols.

Ensures all Protocols are importable, runtime_checkable where required,
and have the expected attribute surface. Concrete implementations live
in later phases (Phase 2 constraints, Phase 3 components, etc.) — this
test only verifies the contract surface.
"""

from __future__ import annotations

import inspect

from app.domain.transition import api

def test_all_protocols_importable() -> None:
    names = [
        "ScoringComponent",
        "HardConstraint",
        "WeightOverlay",
        "PickerRule",
        "RecipeBuilder",
        "VocalActivityDetector",
        "HarmonicMotifDetector",
        "TransitionEvaluatorProtocol",
    ]
    for name in names:
        proto = getattr(api, name, None)
        assert proto is not None, f"{name} not exported from api.py"
        assert inspect.isclass(proto), f"{name} must be a class/Protocol"

def test_scoring_component_signature() -> None:
    sig = inspect.signature(api.ScoringComponent.score)
    params = list(sig.parameters)
    assert "from_t" in params and "to_t" in params

def test_runtime_checkable_protocols() -> None:
    # These four are used in DI / mock testing → must be runtime-checkable.
    from typing import _ProtocolMeta  # type: ignore[attr-defined]
    runtime = [
        api.ScoringComponent, api.HardConstraint, api.WeightOverlay,
        api.PickerRule, api.RecipeBuilder, api.VocalActivityDetector,
        api.HarmonicMotifDetector,
    ]
    for proto in runtime:
        assert getattr(proto, "_is_runtime_protocol", False), (
            f"{proto.__name__} should be @runtime_checkable"
        )
```

- [ ] **Step 2: Run test — expect import error**

```bash
uv run pytest tests/domain/transition/test_api_protocols.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.domain.transition.api'`.

- [ ] **Step 3: Create `api.py`**

Write `app/domain/transition/api.py`:

```python
"""Protocols for the transition subsystem (v1.5.0 architecture refactor).

These Protocols define the structural contracts that concrete
implementations in scoring/, constraints/, picker/, recipe/ satisfy.
The orchestrator (TransitionEvaluator) and registries depend only on
these abstractions — concrete classes are plug-in Strategy instances.

All Protocols here are intended for DI; runtime_checkable lets tests
assert isinstance against them. Concrete implementations live in
later modules — this file has no logic, only contracts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

# Type aliases shared by scalar/bulk methods.
FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]
BoolArr = npt.NDArray[np.bool_]

@runtime_checkable
class ScoringComponent(Protocol):
    """One component of the weighted scoring formula.

    Each component carries its own weight, its own feature dependencies,
    and its own scalar/bulk implementations. Components are composed by
    CompositeScorer (see scoring/composite.py).
    """

    name: str
    default_weight: float

    def score(self, from_t: "TrackFeatures", to_t: "TrackFeatures") -> float: ...

    def score_pairs(self, fa: "FeatureArrays", ia: IntArr, ib: IntArr) -> FloatArr: ...

@runtime_checkable
class HardConstraint(Protocol):
    """A hard-reject gate. Chain of constraints; first match wins."""

    name: str

    def check(
        self,
        from_t: "TrackFeatures",
        to_t: "TrackFeatures",
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> str | None: ...

    def check_bulk(self, fa: "FeatureArrays", ia: IntArr, ib: IntArr) -> BoolArr: ...

@runtime_checkable
class WeightOverlay(Protocol):
    """Transformer of base weights given context.

    Overlays are applied as a chain. The terminal RenormaliseOverlay
    ensures the resulting weights sum to 1.0.
    """

    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: "TransitionIntent | None" = None,
        section_context: "SectionContext | None" = None,
    ) -> dict[str, float]: ...

@runtime_checkable
class VocalActivityDetector(Protocol):
    """Decide whether a track has vocal-active sections.

    Default impl uses 3 spectral proxies (SpectralVocalActivityDetector).
    Phase 3 stem-separation work will add StemVocalActivityDetector(stem_provider).
    """

    def is_active(self, t: "TrackFeatures") -> bool: ...
    def is_low(self, t: "TrackFeatures") -> bool: ...
    def data_missing(self, t: "TrackFeatures") -> bool: ...

@runtime_checkable
class HarmonicMotifDetector(Protocol):
    """Decide whether a track carries a harmonic motif suitable for sustain."""

    def is_motif(self, t: "TrackFeatures") -> bool: ...

@runtime_checkable
class PickerRule(Protocol):
    """One branch of the picker decision tree.

    Rules are iterated as Chain of Responsibility — first non-None
    return wins. Pass-through (None) defers to the next rule.
    """

    name: str

    def evaluate(
        self,
        score: "TransitionScore",
        from_t: "TrackFeatures",
        to_t: "TrackFeatures",
        *,
        section_context: "SectionContext | None",
        subgenre_pair: "SubgenrePairType | None",
        intent: "TransitionIntent | None",
    ) -> "PickerDecision | None": ...

@runtime_checkable
class RecipeBuilder(Protocol):
    """Build a stem-keyframe envelope for one NeuralMixTransition preset.

    Concrete builders typically extend BaseRecipeBuilder (Template
    Method) but can also implement RecipeBuilder directly for full
    control over A-side / B-side / FX layout.
    """

    transition: "NeuralMixTransition"

    def build(self, bars: int) -> "KeyframeBundle": ...

class TransitionEvaluatorProtocol(Protocol):
    """Orchestrator surface — DI containers and callers depend on this.

    Not @runtime_checkable: this is a structural contract for type
    checking, not for isinstance gates.
    """

    def evaluate(
        self,
        from_t: "TrackFeatures",
        to_t: "TrackFeatures",
        *,
        intent: "TransitionIntent | None" = None,
        section_context: "SectionContext | None" = None,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> "TransitionScore": ...

    def evaluate_intents(
        self,
        from_t: "TrackFeatures",
        to_t: "TrackFeatures",
        intents: Iterable["TransitionIntent"],
        *,
        section_context: "SectionContext | None" = None,
    ) -> dict["TransitionIntent", "TransitionScore"]: ...

    def evaluate_pairs(
        self,
        tracks: Sequence["TrackFeatures"],
        pairs: Sequence[tuple[int, int]],
        intents: Iterable["TransitionIntent"],
        *,
        section_context: "SectionContext | None" = None,
    ) -> dict[tuple[int, int, str], float]: ...

# Forward-ref placeholders — all resolve via PEP 563 string annotations.
# Concrete types live in: app.shared.features (TrackFeatures), enums.py
# (TransitionIntent, NeuralMixTransition, SubgenrePairType), score.py
# (TransitionScore), section_context.py (SectionContext),
# picker/api.py (PickerDecision), recipe/api.py (KeyframeBundle),
# scoring/bulk/arrays.py (FeatureArrays).
```

- [ ] **Step 4: Run test — expect pass**

```bash
uv run pytest tests/domain/transition/test_api_protocols.py -q
```

Expected: `=== 3 passed in ...===`.

- [ ] **Step 5: Mypy + ruff per-file**

```bash
uv run ruff check app/domain/transition/api.py tests/domain/transition/test_api_protocols.py
uv run mypy app/domain/transition/api.py
```

Expected: no output (silent success).

- [ ] **Step 6: Commit**

```bash
git add app/domain/transition/api.py tests/domain/transition/test_api_protocols.py
git commit -m "feat(transition): add api.py with 8 Protocols for v1.5.0 architecture"
```

---

### Task 1.3: Create skeleton directories with `__init__.py` shims

For each subdir, create only the `__init__.py` stub that re-exports from the **current** location. Concrete migrations happen in Phases 2-6.

**Pattern (apply identically to all 9 subdirs):**

For each `<subdir>` in:
```text
enums.py (file, not dir)
kernels/
scoring/
scoring/components/
scoring/overlays/
scoring/bulk/
constraints/
constraints/specs/
picker/
picker/proxies/
picker/rules/
recipe/
recipe/envelopes/
recipe/builders/
context/
neural_mix/
```

Tasks 1.3.1 through 1.3.15 — each:

- [ ] **Step 1: `mkdir -p` the directory** (skip for file-only `enums.py`).
- [ ] **Step 2: Create `__init__.py`** with a one-line module docstring + a re-export of the current source-of-truth name. Example:

`app/domain/transition/enums.py`:

```python
"""Enums for the transition subsystem.

Phase 1 skeleton: re-exports current enums for now; Phase 3 will move
NeuralMixStem and NeuralMixTransition here as primary definitions.
"""

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.section_context import SectionPairClass
from app.domain.transition.subgenre_rules import SubgenrePairType

__all__ = [
    "NeuralMixStem",
    "NeuralMixTransition",
    "SectionPairClass",
    "SubgenrePairType",
    "TransitionIntent",
]
```

`app/domain/transition/kernels/__init__.py`:

```python
"""Pure math primitives for scoring (Phase 1 skeleton).

Phase 3 will move bpm_distance, cosine_similarity, correlation here
as primary; for now they re-export from math_helpers.py.
"""

from app.domain.transition.math_helpers import bpm_distance, correlation, cosine_similarity

__all__ = ["bpm_distance", "correlation", "cosine_similarity"]
```

Repeat for each subdir with appropriate re-exports. **Empty subdirs** (`scoring/components/`, `recipe/builders/`, `picker/rules/`, `picker/proxies/`, `constraints/specs/`, `recipe/envelopes/`, `scoring/overlays/`, `scoring/bulk/`) get a minimal docstring-only `__init__.py`:

```python
"""<Subsystem> — Phase 1 placeholder; concrete impls land in Phases 2-6."""
```

- [ ] **Step 3: Verify every new path imports**

After each subdir creation, run:

```bash
uv run python -c "import app.domain.transition.<subdir_with_dots>; print('ok')"
```

- [ ] **Step 4: After all 15 sub-paths created, run full smoke test**

```bash
uv run python -c "
import app.domain.transition.api
import app.domain.transition.enums
import app.domain.transition.kernels
import app.domain.transition.scoring
import app.domain.transition.scoring.components
import app.domain.transition.scoring.overlays
import app.domain.transition.scoring.bulk
import app.domain.transition.constraints
import app.domain.transition.constraints.specs
import app.domain.transition.picker
import app.domain.transition.picker.proxies
import app.domain.transition.picker.rules
import app.domain.transition.recipe
import app.domain.transition.recipe.envelopes
import app.domain.transition.recipe.builders
import app.domain.transition.context
import app.domain.transition.neural_mix
print('all 17 paths import cleanly')
"
```

Expected: `all 17 paths import cleanly`. Note: `picker/__init__.py` will collide with existing `picker.py` — handled in Phase 6. For Phase 1 we have `picker/` (directory) and `picker.py` (legacy) — Python prefers the package. **Verify** that legacy `from app.domain.transition.picker import pick_neural_mix` still works:

```bash
uv run python -c "from app.domain.transition.picker import pick_neural_mix; print(pick_neural_mix)"
```

This works **only if `picker/__init__.py`** re-exports `pick_neural_mix`. So in Phase 1 the `picker/__init__.py` must be:

```python
"""Picker — Phase 1 skeleton; CoR pipeline lands in Phase 6.

Picker.py (legacy module) is shadowed by this package; we re-export the
full surface from the package's __init__.py to keep backward compat.
"""

import importlib as _importlib

_legacy = _importlib.import_module("app.domain.transition._picker_legacy")

PickerDecision = _legacy.PickerDecision
pick_neural_mix = _legacy.pick_neural_mix
build_recipe_for_pair = _legacy.build_recipe_for_pair

__all__ = ["PickerDecision", "build_recipe_for_pair", "pick_neural_mix"]
```

**Important detail.** Creating `picker/` directory while `picker.py` exists requires renaming `picker.py` to `_picker_legacy.py` first to avoid name collision with the package. This rename is a separate atomic step:

- [ ] **Step 4a (only for picker)**: Rename `picker.py` → `_picker_legacy.py`, then create `picker/` directory and `picker/__init__.py` re-export shim shown above. Apply same dual-handling to `recipe.py` → `_recipe_legacy.py`, `scoring/` (no current `scoring.py`, plain), `constraints/` (no current `constraints.py`, plain). Specifically: `picker.py`, `recipe.py`, `builders.py`, `neural_mix.py`, `bulk_scorer.py`, `scorer.py` all become `_*_legacy.py` shadows in later phases — but for Phase 1 only `picker.py` and `recipe.py` and `builders.py` and `neural_mix.py` need renaming because the corresponding **directories** are being introduced. `scorer.py` and `bulk_scorer.py` and `subgenre_rules.py` and `section_context.py` etc. have no directory conflict and stay where they are.

  Concrete operations for Phase 1 collisions:

  ```bash
  git mv app/domain/transition/picker.py app/domain/transition/_picker_legacy.py
  git mv app/domain/transition/recipe.py app/domain/transition/_recipe_legacy.py
  git mv app/domain/transition/builders.py app/domain/transition/_builders_legacy.py
  git mv app/domain/transition/neural_mix.py app/domain/transition/_neural_mix_legacy.py
  ```

  Then update internal imports inside `__init__.py` of the new packages to point at `_*_legacy` modules. All existing `from app.domain.transition.picker import X` calls in handlers/tools/resources still work because the **package** `picker/` re-exports the same names.

  Then update three callers that import from `.builders` or `.neural_mix` directly (caught by grep):

  ```bash
  grep -rn "from app.domain.transition.builders\|from app.domain.transition.neural_mix\|from app.domain.transition.recipe\|from app.domain.transition.picker" app/ tests/ --include="*.py" | grep -v "_legacy" | wc -l
  ```

  For each call site, replace `from app.domain.transition.<old> import X` with `from app.domain.transition.<new> import X` (where `<new>` is the new package name, identical to old). The package `__init__.py` re-exports make this a no-op rename in caller code. **No caller changes needed** — package shadows the module.

- [ ] **Step 5: Run full test suite + golden tests**

```bash
uv run pytest tests/domain/transition/ -q
```

Expected: every test still passes (no regression). Confirms re-exports are correct.

- [ ] **Step 6: Run `make check`**

```bash
make check 2>&1 | tail -10
```

Expected: all green.

- [ ] **Step 7: Commit Phase 1 skeleton**

```bash
git add app/domain/transition/
git commit -m "feat(transition): Phase 1 skeleton — package layout + re-export shims

17 new modules/packages introduced as empty/shim parents for the v1.5.0
refactor. Legacy modules renamed to _<name>_legacy.py to avoid package
name collision; new package __init__.py re-exports preserve the public
API surface byte-identical. Zero behaviour change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 1.4: Phase 1 gate

- [ ] **Step 1: Full pre-PR check**

```bash
make check && uv run pytest tests/domain/transition/test_golden_*.py -q && uv run pytest tests/domain/transition/test_public_api_freeze.py -q && uv run pytest tests/domain/transition/test_bulk_scorer_parity.py -q
```

Expected: all green.

- [ ] **Step 2: Confirm `__all__` still 21**

```bash
uv run python -c "import app.domain.transition as m; print(len(m.__all__))"
```

Expected: `21`.

- [ ] **Step 3: Push + PR**

```bash
git push -u origin refactor/transition-arch-v1-protocols
gh pr create --base main --title "refactor(transition): Phase 1 — Protocols + package skeleton" --body "Empty package skeleton with Protocols defined; zero behaviour change. Re-export shims preserve public API. Phase 1 of v1.5.0 refactor."
```

- [ ] **Step 4: Memory anchor** — record commit SHA after merge in [Appendix A](#appendix-a--memory-anchors).

---

# Phase 2 — Constraints Migration (PR 2)

**Branch:** from `main` HEAD → `refactor/transition-arch-v2-constraints`.

**Goal:** Decompose `hard_constraints.py:check_hard_constraints` into 3 Spec strategies + Chain. Behaviour identical.

### Task 2.1: Branch up

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b refactor/transition-arch-v2-constraints
```

### Task 2.2: Implement `BpmDifferenceSpec` (TDD)

**Files:**
- Create: `app/domain/transition/constraints/specs/bpm_difference.py`
- Create: `tests/domain/transition/constraints/specs/test_bpm_difference.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for BpmDifferenceSpec hard constraint."""

import numpy as np
import pytest

from app.domain.transition.constraints.specs.bpm_difference import BpmDifferenceSpec
from app.domain.transition.scoring.bulk.arrays import extract_feature_arrays
from app.shared.features import TrackFeatures

def test_passes_when_bpm_within_threshold():
    spec = BpmDifferenceSpec()
    a = TrackFeatures(bpm=125.0)
    b = TrackFeatures(bpm=128.0)
    assert spec.check(a, b) is None

def test_rejects_when_bpm_diff_exceeds_threshold():
    spec = BpmDifferenceSpec()
    a = TrackFeatures(bpm=125.0)
    b = TrackFeatures(bpm=145.0)
    reason = spec.check(a, b)
    assert reason is not None
    assert "BPM diff" in reason

def test_pre_distance_overrides_computation():
    spec = BpmDifferenceSpec()
    a = TrackFeatures(bpm=125.0)
    b = TrackFeatures(bpm=128.0)  # would pass normally
    reason = spec.check(a, b, pre_bpm_dist=15.0)  # override → fail
    assert reason is not None

def test_passes_when_bpm_missing():
    spec = BpmDifferenceSpec()
    a = TrackFeatures()
    b = TrackFeatures()
    assert spec.check(a, b) is None

def test_check_bulk_matches_scalar():
    spec = BpmDifferenceSpec()
    tracks = [TrackFeatures(bpm=125.0), TrackFeatures(bpm=145.0), TrackFeatures(bpm=128.0)]
    fa = extract_feature_arrays(tracks)
    ia = np.array([0, 0, 1], dtype=np.int64)
    ib = np.array([1, 2, 2], dtype=np.int64)
    bulk_mask = spec.check_bulk(fa, ia, ib)
    scalar_mask = np.array([spec.check(tracks[a], tracks[b]) is not None for a, b in zip(ia, ib)])
    np.testing.assert_array_equal(bulk_mask, scalar_mask)
```

- [ ] **Step 2: Implement**

```python
"""BpmDifferenceSpec — hard reject when BPM gap exceeds threshold."""

from __future__ import annotations

import numpy as np

from app.config import get_settings
from app.domain.transition.api import BoolArr, IntArr
from app.domain.transition.kernels.bpm_distance import bpm_distance, bpm_distance_bulk
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.shared.features import TrackFeatures

class BpmDifferenceSpec:
    name = "bpm_difference"

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> str | None:
        settings = get_settings().transition
        if pre_bpm_dist is not None:
            diff = pre_bpm_dist
        elif from_t.bpm is not None and to_t.bpm is not None:
            diff = bpm_distance(from_t.bpm, to_t.bpm)
        else:
            return None
        if diff > settings.hard_reject_bpm_diff:
            return f"BPM diff {diff:.1f} > {settings.hard_reject_bpm_diff}"
        return None

    def check_bulk(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> BoolArr:
        settings = get_settings().transition
        bpm_a = fa.bpm[ia]
        bpm_b = fa.bpm[ib]
        present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
        diff = bpm_distance_bulk(bpm_a, bpm_b)
        return present & (diff > settings.hard_reject_bpm_diff)
```

- [ ] **Step 3: Run test → pass**

```bash
uv run pytest tests/domain/transition/constraints/specs/test_bpm_difference.py -q
```

Expected: `=== 5 passed in ...===`.

- [ ] **Step 4: Commit**

```bash
git add app/domain/transition/constraints/specs/bpm_difference.py tests/domain/transition/constraints/specs/test_bpm_difference.py
git commit -m "feat(transition): add BpmDifferenceSpec hard-constraint strategy"
```

### Task 2.3: Implement `CamelotDistanceSpec`

Apply same pattern as Task 2.2 with these specifics:
- `name = "camelot_distance"`
- Scalar reads `from_t.key_code` / `to_t.key_code`, calls `camelot_distance(a, b)` from `app.domain.camelot.wheel`. Threshold: `settings.hard_reject_camelot_dist`. Message: `f"Camelot distance {dist} >= {threshold}"`.
- Bulk: use `from app.domain.transition.kernels.camelot_lookup import camelot_distance_table`. Returns `(present) & (dist >= threshold)`.

Test file: `tests/domain/transition/constraints/specs/test_camelot_distance.py` — five tests mirroring BpmDifferenceSpec test layout (`within / exceeds / pre_override / missing / bulk_matches_scalar`).

Commit: `feat(transition): add CamelotDistanceSpec hard-constraint strategy`.

### Task 2.4: Implement `EnergyGapSpec`

Apply same pattern. Specifics:
- `name = "energy_gap"`
- Scalar reads `integrated_lufs`, computes `abs(b - a)`. Threshold: `settings.hard_reject_energy_gap_lufs`. Message: `f"Energy gap {gap:.1f} LUFS > {threshold}"`.
- Bulk: NaN-aware abs diff.

Commit: `feat(transition): add EnergyGapSpec hard-constraint strategy`.

### Task 2.5: Implement `HardConstraintChain`

**Files:**
- Create: `app/domain/transition/constraints/chain.py`
- Create: `app/domain/transition/constraints/__init__.py` (DEFAULT_CONSTRAINTS tuple)
- Create: `tests/domain/transition/constraints/test_chain.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for HardConstraintChain."""

import numpy as np

from app.domain.transition.constraints import DEFAULT_CONSTRAINTS
from app.domain.transition.constraints.chain import HardConstraintChain
from app.domain.transition.constraints.specs.bpm_difference import BpmDifferenceSpec
from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.domain.transition.constraints.specs.energy_gap import EnergyGapSpec
from app.domain.transition.scoring.bulk.arrays import extract_feature_arrays
from app.shared.features import TrackFeatures

def test_default_chain_order():
    assert tuple(c.name for c in DEFAULT_CONSTRAINTS) == (
        "bpm_difference", "camelot_distance", "energy_gap",
    )

def test_chain_pass():
    chain = HardConstraintChain(DEFAULT_CONSTRAINTS)
    a = TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-8.0)
    b = TrackFeatures(bpm=128.0, key_code=8, integrated_lufs=-7.5)
    rej = chain.check(a, b)
    assert rej is None

def test_chain_first_match_wins():
    chain = HardConstraintChain(DEFAULT_CONSTRAINTS)
    a = TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-8.0)
    b = TrackFeatures(bpm=145.0, key_code=20, integrated_lufs=0.0)  # all three fail
    rej = chain.check(a, b)
    assert rej is not None
    assert rej.hard_reject
    assert "BPM diff" in (rej.reject_reason or "")  # bpm wins (first in chain)

def test_check_bulk_returns_any_violation():
    chain = HardConstraintChain(DEFAULT_CONSTRAINTS)
    tracks = [
        TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-8.0),
        TrackFeatures(bpm=145.0, key_code=8, integrated_lufs=-8.0),  # bpm fails
        TrackFeatures(bpm=125.0, key_code=20, integrated_lufs=-8.0),  # camelot fails
    ]
    fa = extract_feature_arrays(tracks)
    ia = np.array([0, 0, 0], dtype=np.int64)
    ib = np.array([0, 1, 2], dtype=np.int64)
    mask = chain.check_bulk(fa, ia, ib)
    assert list(mask) == [False, True, True]
```

- [ ] **Step 2: Implement chain**

```python
"""Chain of Responsibility for hard constraints.

Iterates DEFAULT_CONSTRAINTS first-match-wins; if any spec returns a
reason string, wraps it into a TransitionScore(hard_reject=True) and
short-circuits. Otherwise returns None.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.domain.transition.api import BoolArr, HardConstraint, IntArr
from app.domain.transition.score import TransitionScore
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.shared.features import TrackFeatures

class HardConstraintChain:
    def __init__(self, constraints: Sequence[HardConstraint]) -> None:
        self._constraints = tuple(constraints)

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> TransitionScore | None:
        for spec in self._constraints:
            reason = spec.check(
                from_t, to_t,
                pre_bpm_dist=pre_bpm_dist,
                pre_key_dist=pre_key_dist,
                pre_energy_delta=pre_energy_delta,
            )
            if reason is not None:
                return TransitionScore(hard_reject=True, reject_reason=reason)
        return None

    def check_bulk(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> BoolArr:
        mask = np.zeros(len(ia), dtype=np.bool_)
        for spec in self._constraints:
            mask = mask | spec.check_bulk(fa, ia, ib)
        return mask
```

And `__init__.py`:

```python
"""Hard-constraint registry — chain of Spec strategies.

Order matters: first-match-wins in the chain. Default order matches
the legacy check_hard_constraints sequence (BPM → Camelot → energy).
"""

from app.domain.transition.api import HardConstraint
from app.domain.transition.constraints.chain import HardConstraintChain
from app.domain.transition.constraints.specs.bpm_difference import BpmDifferenceSpec
from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.domain.transition.constraints.specs.energy_gap import EnergyGapSpec

DEFAULT_CONSTRAINTS: tuple[HardConstraint, ...] = (
    BpmDifferenceSpec(),
    CamelotDistanceSpec(),
    EnergyGapSpec(),
)

DEFAULT_HARD_CONSTRAINT_CHAIN = HardConstraintChain(DEFAULT_CONSTRAINTS)

__all__ = ["DEFAULT_CONSTRAINTS", "DEFAULT_HARD_CONSTRAINT_CHAIN", "HardConstraintChain"]
```

- [ ] **Step 3: Run tests → pass**

```bash
uv run pytest tests/domain/transition/constraints/ -q
```

Expected: `=== 19 passed in ...===` (5 BPM + 5 Camelot + 5 Energy + 4 chain).

- [ ] **Step 4: Commit**

```bash
git add app/domain/transition/constraints/chain.py app/domain/transition/constraints/__init__.py tests/domain/transition/constraints/test_chain.py
git commit -m "feat(transition): add HardConstraintChain + DEFAULT_CONSTRAINTS"
```

### Task 2.6: Replace `hard_constraints.py` body with adapter

**Files:**
- Modify: `app/domain/transition/hard_constraints.py`

- [ ] **Step 1: Read current file** — confirm it's `check_hard_constraints` function.
- [ ] **Step 2: Replace body**

```python
"""Adapter — preserves the legacy check_hard_constraints signature.

Wraps HardConstraintChain.check(...) for backward compatibility.
All scoring math lives in constraints/specs/*.
"""

from __future__ import annotations

from app.domain.transition.constraints import DEFAULT_HARD_CONSTRAINT_CHAIN
from app.domain.transition.score import TransitionScore
from app.shared.features import TrackFeatures

def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> TransitionScore | None:
    """Return a zero-score rejection or None if all constraints pass."""
    return DEFAULT_HARD_CONSTRAINT_CHAIN.check(
        from_t, to_t,
        pre_bpm_dist=pre_bpm_dist,
        pre_key_dist=pre_key_dist,
        pre_energy_delta=pre_energy_delta,
    )
```

- [ ] **Step 3: Run all transition tests + golden**

```bash
uv run pytest tests/domain/transition/ -q
```

Expected: every existing test green + new constraint tests green.

- [ ] **Step 4: Commit**

```bash
git add app/domain/transition/hard_constraints.py
git commit -m "refactor(transition): hard_constraints.py now adapts to HardConstraintChain"
```

### Task 2.7: Update `bulk_scorer.hard_reject_mask_bulk` adapter

Same pattern: replace body with `DEFAULT_HARD_CONSTRAINT_CHAIN.check_bulk(fa, ia, ib)`. Run all bulk parity tests; they must remain green.

Commit: `refactor(transition): hard_reject_mask_bulk now adapts to HardConstraintChain`.

### Task 2.8: Phase 2 gate

- [ ] **Step 1:** `make check` + all golden tests green.
- [ ] **Step 2:** Push + open PR titled "refactor(transition): Phase 2 — hard constraints to Strategy + Chain".
- [ ] **Step 3:** Memory anchor in [Appendix A](#appendix-a--memory-anchors).

---

# Phase 3 — Scoring Components + Composite + Overlays (PR 3, biggest)

**Branch:** from `main` → `refactor/transition-arch-v3-scoring`.

**Goal:** Distribute `neural_mix.py` + `scorer.py` (overlay logic) + `bulk_scorer.py` + `components/` into the new `scoring/` layout. Behaviour byte-identical; golden + bulk-parity tests are the contract.

### Task 3.1: Branch up + kernel migration

**Files:**
- Create: `app/domain/transition/kernels/bpm_distance.py`
- Create: `app/domain/transition/kernels/camelot_lookup.py`
- Create: `app/domain/transition/kernels/cosine.py`
- Create: `app/domain/transition/kernels/gauss.py`
- Modify: `app/domain/transition/kernels/__init__.py` (re-export both new and legacy paths).
- Modify: `app/domain/transition/math_helpers.py` (re-export from kernels).

- [ ] **Step 1: Branch up**
  ```bash
  git checkout main && git pull --ff-only origin main
  git checkout -b refactor/transition-arch-v3-scoring
  ```
- [ ] **Step 2: Move `bpm_distance` from `math_helpers.py` to `kernels/bpm_distance.py`**. Add bulk variant `bpm_distance_bulk(a: FloatArr, b: FloatArr) -> FloatArr` (copy from `bulk_scorer.py:_bpm_distance_bulk`).
- [ ] **Step 3: Move `cosine_similarity` to `kernels/cosine.py`**. Add bulk variant `cosine_similarity_bulk(matrix, ia, ib)` from `bulk_scorer.py:_cosine_similarity_bulk`.
- [ ] **Step 4: Move `correlation` to `kernels/correlation.py`** (scalar only — bulk not needed).
- [ ] **Step 5: Move `_camelot_distance_table` from `bulk_scorer.py` to `kernels/camelot_lookup.py`** as `camelot_distance_table()`. Also export module-level `_CAMELOT_DISTANCE` = table.
- [ ] **Step 6: Create `kernels/gauss.py`** with `gauss_similarity(delta, sigma)` scalar + bulk wrapping the `exp(-(x**2) / (2*sigma**2))` formula. Replace inline usage in BpmComponent / EnergyComponent / etc.
- [ ] **Step 7: Update `math_helpers.py` body** to re-export from kernels for backward compat.
- [ ] **Step 8: Run all tests** — golden + bulk-parity must remain green.
- [ ] **Step 9: Commit**: `refactor(transition): migrate math helpers into kernels/ subpackage`.

### Task 3.2: Migrate `FeatureArrays` to `scoring/bulk/arrays.py`

- [ ] **Step 1:** Move `FeatureArrays`, `_scalar_arr`, `_bool_arr`, `_int_arr`, `_vector_matrix`, `extract_feature_arrays`, the `_MFCC_DIM` / `_TONNETZ_DIM` / `_ENERGY_BAND_DIM` / `_BEAT_LOUDNESS_DIM` constants, and the `_NAN` sentinel from `bulk_scorer.py` to `scoring/bulk/arrays.py`. Identical implementation.
- [ ] **Step 2:** Update `bulk_scorer.py` to re-export from `scoring.bulk.arrays`.
- [ ] **Step 3:** Run bulk parity tests.
- [ ] **Step 4:** Commit: `refactor(transition): move FeatureArrays to scoring/bulk/arrays.py`.

### Task 3.3: Implement `BpmComponent` (representative full TDD task)

**Files:**
- Create: `app/domain/transition/scoring/components/bpm.py`
- Create: `tests/domain/transition/scoring/components/test_bpm.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for BpmComponent (scoring/components/bpm.py)."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.transition.components.bpm import score_bpm as legacy_score_bpm
from app.domain.transition.scoring.bulk.arrays import extract_feature_arrays
from app.domain.transition.scoring.components.bpm import BpmComponent
from app.shared.features import TrackFeatures

def test_scalar_matches_legacy_for_normal_pair():
    comp = BpmComponent()
    a = TrackFeatures(bpm=125.0, bpm_stability=0.9, bpm_confidence=0.85, variable_tempo=False)
    b = TrackFeatures(bpm=127.0, bpm_stability=0.9, bpm_confidence=0.85, variable_tempo=False)
    assert comp.score(a, b) == pytest.approx(legacy_score_bpm(a, b), abs=1e-12)

def test_scalar_neutral_when_bpm_missing():
    comp = BpmComponent()
    a = TrackFeatures()
    b = TrackFeatures()
    assert comp.score(a, b) == 0.5

def test_default_weight_matches_DEFAULT_WEIGHTS():
    from app.domain.transition.weights import DEFAULT_WEIGHTS
    assert BpmComponent().default_weight == DEFAULT_WEIGHTS["bpm"]

def test_bulk_matches_scalar_across_pool():
    comp = BpmComponent()
    pool = [
        TrackFeatures(bpm=125.0, bpm_stability=0.9, bpm_confidence=0.85, variable_tempo=False),
        TrackFeatures(bpm=132.0, bpm_stability=0.8, bpm_confidence=0.7, variable_tempo=True),
        TrackFeatures(),  # missing all
        TrackFeatures(bpm=120.0, bpm_stability=None, bpm_confidence=None, variable_tempo=None),
    ]
    fa = extract_feature_arrays(pool)
    pairs = [(a, b) for a in range(len(pool)) for b in range(len(pool)) if a != b]
    ia = np.array([p[0] for p in pairs], dtype=np.int64)
    ib = np.array([p[1] for p in pairs], dtype=np.int64)
    bulk = comp.score_pairs(fa, ia, ib)
    scalar = np.array([comp.score(pool[a], pool[b]) for a, b in pairs], dtype=np.float64)
    np.testing.assert_allclose(bulk, scalar, atol=1e-9)
```

- [ ] **Step 2:** Run test → expect import error.
- [ ] **Step 3: Implement**

```python
"""BpmComponent — tempo compatibility scoring (scalar + bulk co-located).

Scalar logic mirrors the legacy components/bpm.py:score_bpm function.
Bulk logic mirrors bulk_scorer.py:score_bpm_bulk. Both are kept in
lockstep — parity tested in test_bpm.py.
"""

from __future__ import annotations

import math

import numpy as np

from app.config import get_settings
from app.domain.transition.api import FloatArr, IntArr
from app.domain.transition.kernels.bpm_distance import bpm_distance, bpm_distance_bulk
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.domain.transition.weights import (
    BPM_CONFIDENCE_PENALTY_FLOOR,
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
    DEFAULT_WEIGHTS,
)
from app.shared.features import TrackFeatures

class BpmComponent:
    name = "bpm"
    default_weight: float = DEFAULT_WEIGHTS["bpm"]

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        settings = get_settings().transition
        if from_t.bpm is None or to_t.bpm is None:
            return 0.5
        delta = bpm_distance(from_t.bpm, to_t.bpm)
        score = math.exp(-(delta**2) / (2 * BPM_GAUSS_SIGMA**2))
        if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
            score *= max(BPM_STABILITY_FLOOR, min(from_t.bpm_stability, to_t.bpm_stability))
        if from_t.bpm_confidence is not None and to_t.bpm_confidence is not None:
            min_conf = min(from_t.bpm_confidence, to_t.bpm_confidence)
            if min_conf < settings.scoring_bpm_confidence_floor:
                score *= max(
                    BPM_CONFIDENCE_PENALTY_FLOOR,
                    min_conf / settings.scoring_bpm_confidence_floor,
                )
        if (from_t.variable_tempo is True) or (to_t.variable_tempo is True):
            score = max(0.0, score - settings.scoring_variable_tempo_penalty)
        return score

    def score_pairs(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
        settings = get_settings().transition
        bpm_a = fa.bpm[ia]
        bpm_b = fa.bpm[ib]
        present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
        delta = bpm_distance_bulk(bpm_a, bpm_b)
        score = np.exp(-(delta**2) / (2 * BPM_GAUSS_SIGMA**2))
        stab_a = fa.bpm_stability[ia]
        stab_b = fa.bpm_stability[ib]
        stab_present = ~(np.isnan(stab_a) | np.isnan(stab_b))
        stab_factor = np.where(
            stab_present, np.maximum(BPM_STABILITY_FLOOR, np.minimum(stab_a, stab_b)), 1.0
        )
        score = score * stab_factor
        conf_a = fa.bpm_confidence[ia]
        conf_b = fa.bpm_confidence[ib]
        conf_present = ~(np.isnan(conf_a) | np.isnan(conf_b))
        min_conf = np.minimum(conf_a, conf_b)
        floor = settings.scoring_bpm_confidence_floor
        needs_penalty = conf_present & (min_conf < floor)
        conf_factor = np.where(
            needs_penalty,
            np.maximum(BPM_CONFIDENCE_PENALTY_FLOOR, min_conf / floor),
            1.0,
        )
        score = score * conf_factor
        var_a = fa.variable_tempo[ia]
        var_b = fa.variable_tempo[ib]
        var_penalty = (var_a | var_b).astype(np.float64) * settings.scoring_variable_tempo_penalty
        score = np.maximum(0.0, score - var_penalty)
        return np.where(present, score, 0.5)
```

- [ ] **Step 4:** Run test → pass.
- [ ] **Step 5: Commit**: `feat(transition): add BpmComponent scalar+bulk co-located`.

### Tasks 3.4-3.8: Other 5 ScoringComponents (apply BpmComponent pattern)

For each of `EnergyComponent`, `DrumsComponent`, `BassComponent`, `HarmonicsComponent`, `VocalsComponent`:

- File: `app/domain/transition/scoring/components/<name>.py`.
- Test: `tests/domain/transition/scoring/components/test_<name>.py`.
- Scalar source: copy from current `app/domain/transition/components/<name>.py` (for bpm/energy) or from `neural_mix.py:score_<stem>_compat` (for drums/bass/harmonics/vocals). Same math, same magic numbers.
- Bulk source: copy from `bulk_scorer.py:score_<name>_bulk` body verbatim into the `score_pairs` method.
- `name` field: `"energy"` / `"drums"` / `"bass"` / `"harmonics"` / `"vocals"`.
- `default_weight`: from `DEFAULT_WEIGHTS[name]`.
- Tests mirror Task 3.3 structure: 4 tests each (scalar matches legacy, missing fields neutral, weight matches DEFAULT_WEIGHTS, bulk matches scalar across pool).
- Commit per component: `feat(transition): add <Name>Component scalar+bulk co-located`.

### Task 3.9: Migrate Neural-Mix composite + dataclass + weight matrix

**Files:**
- Create: `app/domain/transition/neural_mix/weight_matrix.py` — `TRANSITION_STEM_WEIGHTS`, `TRANSITION_ENERGY_BIAS`, `NEURAL_MIX_STEMS`, `TRANSITION_TYPES`.
- Create: `app/domain/transition/neural_mix/energy_bias.py` — `energy_bias_modifier` scalar + bulk.
- Create: `app/domain/transition/neural_mix/score_dataclass.py` — `NeuralMixScore`.
- Create: `app/domain/transition/neural_mix/composite.py` — `NeuralMixScorer`.
- Modify: `app/domain/transition/_neural_mix_legacy.py` (was `neural_mix.py`) — replace body with re-exports.

- [ ] **Step 1:** Move each section of `_neural_mix_legacy.py` to its target file, verbatim. The 4 `score_<stem>_compat` functions stay where they are (they're imported by tests + by `NeuralMixScorer._compute`) but are also imported from `scoring/components/<name>.py`. Net effect: dual source-of-truth for one PR — resolved in PR 3 cleanup substep.
- [ ] **Step 2:** Re-export shim in `_neural_mix_legacy.py`:

```python
"""Re-exports — legacy path; canonical defs in neural_mix/ package."""
from app.domain.transition.neural_mix.weight_matrix import (
    NEURAL_MIX_STEMS, TRANSITION_ENERGY_BIAS, TRANSITION_STEM_WEIGHTS, TRANSITION_TYPES,
)
from app.domain.transition.neural_mix.score_dataclass import NeuralMixScore
from app.domain.transition.neural_mix.composite import NeuralMixScorer
from app.domain.transition.enums import NeuralMixStem, NeuralMixTransition
from app.domain.transition.scoring.components.bass import score_bass_compat  # noqa
from app.domain.transition.scoring.components.drums import score_drums_compat  # noqa
from app.domain.transition.scoring.components.harmonics import score_harmonic_compat  # noqa
from app.domain.transition.scoring.components.vocals import score_vocal_compat  # noqa

__all__ = [
    "NEURAL_MIX_STEMS", "NeuralMixScore", "NeuralMixScorer",
    "NeuralMixStem", "NeuralMixTransition",
    "TRANSITION_ENERGY_BIAS", "TRANSITION_STEM_WEIGHTS", "TRANSITION_TYPES",
    "score_bass_compat", "score_drums_compat",
    "score_harmonic_compat", "score_vocal_compat",
]
```

- [ ] **Step 3:** Run all tests including golden + bulk parity.
- [ ] **Step 4:** Commit: `refactor(transition): split neural_mix.py into focused modules`.

### Task 3.10: `IntentOverlay`

**Files:**
- Create: `app/domain/transition/scoring/overlays/intent.py`
- Test: `tests/domain/transition/scoring/overlays/test_intent.py`

```python
"""IntentOverlay — per-intent base weight selection.

When intent is None, returns the base weights unchanged. Otherwise
replaces base with INTENT_WEIGHT_MODIFIERS[intent] from intent.py.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.section_context import SectionContext

class IntentOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        if intent is None:
            return dict(weights)
        return dict(INTENT_WEIGHT_MODIFIERS[intent])
```

Test: assert `apply(base, intent=None)` returns base copy; `apply(base, intent=RAMP_UP)` returns `INTENT_WEIGHT_MODIFIERS[RAMP_UP]`. Commit.

### Task 3.11: `SectionPairOverlay`

```python
"""SectionPairOverlay — multiply weights by per-section-class lookup."""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.section_context import SectionContext
from app.domain.transition.weights import SECTION_PAIR_OVERLAY

class SectionPairOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        if section_context is None:
            return dict(weights)
        pair_class = section_context.section_pair_class
        overlay = SECTION_PAIR_OVERLAY.get(pair_class.value)
        if overlay is None:
            return dict(weights)
        return {key: weights.get(key, 0.0) * overlay.get(key, 1.0)
                for key in ("bpm", "energy", "drums", "bass", "harmonics", "vocals")}
```

Test + commit.

### Task 3.12: `RenormaliseOverlay`

```python
"""RenormaliseOverlay — terminal step, ensures weights sum to 1.0."""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.section_context import SectionContext

class RenormaliseOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        total = sum(weights.values())
        if total <= 0.0:
            return dict(weights)
        return {k: v / total for k, v in weights.items()}
```

Test + commit.

### Task 3.13: `scoring/overlays/__init__.py:DEFAULT_OVERLAY_CHAIN`

```python
"""Registry of weight overlays. Applied in tuple order.

The legacy _apply_section_overlay logic (scorer.py before v1.5.0)
is equivalent to applying IntentOverlay → SectionPairOverlay →
RenormaliseOverlay. Verified by golden tests.
"""

from app.domain.transition.api import WeightOverlay
from app.domain.transition.scoring.overlays.intent import IntentOverlay
from app.domain.transition.scoring.overlays.renormalise import RenormaliseOverlay
from app.domain.transition.scoring.overlays.section_pair import SectionPairOverlay

DEFAULT_OVERLAY_CHAIN: tuple[WeightOverlay, ...] = (
    IntentOverlay(),
    SectionPairOverlay(),
    RenormaliseOverlay(),
)

__all__ = ["DEFAULT_OVERLAY_CHAIN", "IntentOverlay", "RenormaliseOverlay", "SectionPairOverlay"]
```

### Task 3.14: `CompositeScorer`

**Files:**
- Create: `app/domain/transition/scoring/composite.py`
- Test: `tests/domain/transition/scoring/test_composite.py`

```python
"""CompositeScorer — applies WeightOverlay chain, sums weighted components."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.domain.transition.api import (
    FloatArr, IntArr, ScoringComponent, WeightOverlay,
)
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures

class CompositeScorer:
    def __init__(
        self,
        components: Sequence[ScoringComponent],
        overlays: Sequence[WeightOverlay],
        *,
        base_weights: Mapping[str, float] | None = None,
    ) -> None:
        self._components = tuple(components)
        self._overlays = tuple(overlays)
        self._base = (
            dict(base_weights) if base_weights is not None
            else {c.name: c.default_weight for c in self._components}
        )

    def resolve_weights(
        self,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        weights = dict(self._base)
        for overlay in self._overlays:
            weights = overlay.apply(weights, intent=intent, section_context=section_context)
        return weights

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> tuple[dict[str, float], float]:
        per_component = {c.name: c.score(from_t, to_t) for c in self._components}
        weights = self.resolve_weights(intent=intent, section_context=section_context)
        overall = sum(per_component[name] * weights.get(name, 0.0) for name in per_component)
        return per_component, overall

    def score_pairs(
        self,
        fa: FeatureArrays,
        ia: IntArr,
        ib: IntArr,
        intents: Iterable[TransitionIntent],
        *,
        section_context: SectionContext | None = None,
    ) -> dict[tuple[str, str], FloatArr]:
        per_component_bulk = {c.name: c.score_pairs(fa, ia, ib) for c in self._components}
        result: dict[tuple[str, str], FloatArr] = {}
        for intent in intents:
            weights = self.resolve_weights(intent=intent, section_context=section_context)
            overall = sum(
                per_component_bulk[name] * weights.get(name, 0.0)
                for name in per_component_bulk
            )
            result[(intent.value, "overall")] = overall
        for name, vec in per_component_bulk.items():
            result[("__per_component__", name)] = vec
        return result
```

Tests: assert (a) `resolve_weights` matches old `_apply_section_overlay` output across all (intent × section_pair_class) combinations; (b) `score(a, b)` overall matches legacy `TransitionScorer.score(a, b).overall` for representative pairs.

Commit.

### Task 3.15: `scoring/components/__init__.py:DEFAULT_COMPONENTS`

```python
"""Default scoring components. Add new component = new file + one line here."""

from app.domain.transition.api import ScoringComponent
from app.domain.transition.scoring.components.bass import BassComponent
from app.domain.transition.scoring.components.bpm import BpmComponent
from app.domain.transition.scoring.components.drums import DrumsComponent
from app.domain.transition.scoring.components.energy import EnergyComponent
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent
from app.domain.transition.scoring.components.vocals import VocalsComponent

DEFAULT_COMPONENTS: tuple[ScoringComponent, ...] = (
    BpmComponent(),
    EnergyComponent(),
    DrumsComponent(),
    BassComponent(),
    HarmonicsComponent(),
    VocalsComponent(),
)

__all__ = ["DEFAULT_COMPONENTS", "BassComponent", "BpmComponent", "DrumsComponent",
           "EnergyComponent", "HarmonicsComponent", "VocalsComponent"]
```

### Task 3.16: Replace `bulk_scorer.py` body with re-exports

Replace entire `bulk_scorer.py` with thin re-exports:

```python
"""Backward-compat shim — bulk scoring distributed to scoring/components/.

The score_pairs_bulk function below is preserved for GA hot-path callers;
internally it now dispatches through CompositeScorer.score_pairs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from app.domain.transition.constraints import DEFAULT_HARD_CONSTRAINT_CHAIN
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.scoring.bulk.arrays import (  # noqa: F401
    FeatureArrays, extract_feature_arrays,
)
from app.domain.transition.scoring.components import DEFAULT_COMPONENTS
from app.domain.transition.scoring.components.bass import BassComponent  # noqa: F401
from app.domain.transition.scoring.components.bpm import BpmComponent  # noqa: F401
from app.domain.transition.scoring.components.drums import DrumsComponent  # noqa: F401
from app.domain.transition.scoring.components.energy import EnergyComponent  # noqa: F401
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent  # noqa: F401
from app.domain.transition.scoring.components.vocals import VocalsComponent  # noqa: F401
from app.domain.transition.scoring.composite import CompositeScorer
from app.domain.transition.scoring.overlays import DEFAULT_OVERLAY_CHAIN

# Module-level singleton — matches legacy ALL_INTENTS pre-compute.
_COMPOSITE = CompositeScorer(DEFAULT_COMPONENTS, DEFAULT_OVERLAY_CHAIN)

def score_bpm_bulk(fa: FeatureArrays, ia, ib):  # type: ignore[no-untyped-def]
    return BpmComponent().score_pairs(fa, ia, ib)

def score_energy_bulk(fa: FeatureArrays, ia, ib):  # type: ignore[no-untyped-def]
    return EnergyComponent().score_pairs(fa, ia, ib)

def score_drums_bulk(fa, ia, ib):  # type: ignore[no-untyped-def]
    return DrumsComponent().score_pairs(fa, ia, ib)

def score_bass_bulk(fa, ia, ib):  # type: ignore[no-untyped-def]
    return BassComponent().score_pairs(fa, ia, ib)

def score_harmonics_bulk(fa, ia, ib):  # type: ignore[no-untyped-def]
    return HarmonicsComponent().score_pairs(fa, ia, ib)

def score_vocals_bulk(fa, ia, ib):  # type: ignore[no-untyped-def]
    return VocalsComponent().score_pairs(fa, ia, ib)

def hard_reject_mask_bulk(fa, ia, ib):  # type: ignore[no-untyped-def]
    return DEFAULT_HARD_CONSTRAINT_CHAIN.check_bulk(fa, ia, ib)

def score_pairs_bulk(
    fa: FeatureArrays,
    pairs: Sequence[tuple[int, int]],
    intents: Iterable[TransitionIntent],
) -> dict[tuple[int, int, str], float]:
    intents_list = list(intents)
    if not pairs or not intents_list:
        return {}
    ia = np.fromiter((p[0] for p in pairs), dtype=np.int64, count=len(pairs))
    ib = np.fromiter((p[1] for p in pairs), dtype=np.int64, count=len(pairs))
    rejected = hard_reject_mask_bulk(fa, ia, ib)
    by_intent = _COMPOSITE.score_pairs(fa, ia, ib, intents_list)
    out: dict[tuple[int, int, str], float] = {}
    for intent in intents_list:
        overall = by_intent[(intent.value, "overall")]
        overall = np.where(rejected, 0.0, overall)
        for k, p in enumerate(pairs):
            out[(p[0], p[1], intent.value)] = float(overall[k])
    return out
```

Run bulk parity tests — must remain green at 1e-9 tolerance.

Commit: `refactor(transition): bulk_scorer.py now adapts to CompositeScorer`.

### Task 3.17: Phase 3 gate

- [ ] **Step 1:** `make check` + all golden + bulk parity green.
- [ ] **Step 2:** Push + PR titled "refactor(transition): Phase 3 — scoring layer to Strategy + Composite + Overlays".
- [ ] **Step 3:** Memory anchor.

---

# Phase 4 — TransitionEvaluator + Scorer Adapter (PR 4)

**Branch:** `refactor/transition-arch-v4-evaluator`.

**Goal:** Replace the 3-entry-point `TransitionScorer` with a single `TransitionEvaluator.evaluate*` orchestrator; `TransitionScorer` becomes a thin adapter.

### Task 4.1: Implement `TransitionEvaluator`

**Files:**
- Create: `app/domain/transition/orchestrator.py`
- Create: `tests/domain/transition/test_orchestrator.py`

- [ ] **Step 1: TDD — write `TransitionEvaluator.evaluate` test** matching legacy `TransitionScorer.score` byte-for-byte on representative pairs.
- [ ] **Step 2: Implement**

```python
"""TransitionEvaluator — orchestrator for the v1.5.0 transition scoring.

Single evaluate path replaces score / score_all_intents / score_with_candidates
from the legacy TransitionScorer. Public TransitionScorer becomes a thin
adapter retained for backward compat.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.domain.transition.api import TransitionEvaluatorProtocol
from app.domain.transition.constraints import DEFAULT_HARD_CONSTRAINT_CHAIN
from app.domain.transition.constraints.chain import HardConstraintChain
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.neural_mix.composite import NeuralMixScorer
from app.domain.transition.score import TransitionScore
from app.domain.transition.scoring.bulk.arrays import FeatureArrays, extract_feature_arrays
from app.domain.transition.scoring.components import DEFAULT_COMPONENTS
from app.domain.transition.scoring.composite import CompositeScorer
from app.domain.transition.scoring.overlays import DEFAULT_OVERLAY_CHAIN
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures

_ALL_INTENTS = (
    TransitionIntent.MAINTAIN,
    TransitionIntent.RAMP_UP,
    TransitionIntent.COOL_DOWN,
    TransitionIntent.CONTRAST,
)

class TransitionEvaluator:
    """The orchestrator. Composition wired via DI; defaults match v1.4.0."""

    def __init__(
        self,
        *,
        composite: CompositeScorer | None = None,
        constraints: HardConstraintChain | None = None,
        neural_mix: NeuralMixScorer | None = None,
        base_weights: Mapping[str, float] | None = None,
    ) -> None:
        self._composite = composite or CompositeScorer(
            DEFAULT_COMPONENTS, DEFAULT_OVERLAY_CHAIN, base_weights=base_weights,
        )
        self._constraints = constraints or DEFAULT_HARD_CONSTRAINT_CHAIN
        self._neural = neural_mix or NeuralMixScorer()

    def evaluate(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> TransitionScore:
        rejection = self._constraints.check(
            from_t, to_t,
            pre_bpm_dist=pre_bpm_dist, pre_key_dist=pre_key_dist, pre_energy_delta=pre_energy_delta,
        )
        if rejection is not None:
            return rejection
        per_comp, overall = self._composite.score(
            from_t, to_t, intent=intent, section_context=section_context,
        )
        nm = self._neural.score(from_t, to_t)
        return TransitionScore(
            bpm=per_comp["bpm"], energy=per_comp["energy"],
            drums=per_comp["drums"], bass=per_comp["bass"],
            harmonics=per_comp["harmonics"], vocals=per_comp["vocals"],
            overall=overall, best_transition=nm.best_transition,
            section_pair_class=(
                section_context.section_pair_class.value
                if section_context is not None else None
            ),
        )

    def evaluate_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent] | None = None,
        *,
        section_context: SectionContext | None = None,
    ) -> dict[TransitionIntent, TransitionScore]:
        targets = tuple(intents) if intents is not None else _ALL_INTENTS
        rejection = self._constraints.check(from_t, to_t)
        if rejection is not None:
            return {i: rejection for i in targets}
        per_comp_once = {c.name: c.score(from_t, to_t) for c in self._composite._components}
        nm = self._neural.score(from_t, to_t)
        out: dict[TransitionIntent, TransitionScore] = {}
        for intent in targets:
            weights = self._composite.resolve_weights(intent=intent, section_context=section_context)
            overall = sum(per_comp_once[name] * weights.get(name, 0.0) for name in per_comp_once)
            out[intent] = TransitionScore(
                bpm=per_comp_once["bpm"], energy=per_comp_once["energy"],
                drums=per_comp_once["drums"], bass=per_comp_once["bass"],
                harmonics=per_comp_once["harmonics"], vocals=per_comp_once["vocals"],
                overall=overall, best_transition=nm.best_transition,
                section_pair_class=(
                    section_context.section_pair_class.value
                    if section_context is not None else None
                ),
            )
        return out

    def evaluate_pairs(
        self,
        tracks: Sequence[TrackFeatures],
        pairs: Sequence[tuple[int, int]],
        intents: Iterable[TransitionIntent],
        *,
        section_context: SectionContext | None = None,
    ) -> dict[tuple[int, int, str], float]:
        import numpy as np
        intents_list = list(intents)
        if not pairs or not intents_list:
            return {}
        fa = extract_feature_arrays(tracks)
        ia = np.fromiter((p[0] for p in pairs), dtype=np.int64, count=len(pairs))
        ib = np.fromiter((p[1] for p in pairs), dtype=np.int64, count=len(pairs))
        rejected = self._constraints.check_bulk(fa, ia, ib)
        by_intent = self._composite.score_pairs(fa, ia, ib, intents_list, section_context=section_context)
        out: dict[tuple[int, int, str], float] = {}
        for intent in intents_list:
            overall = by_intent[(intent.value, "overall")]
            overall = np.where(rejected, 0.0, overall)
            for k, p in enumerate(pairs):
                out[(p[0], p[1], intent.value)] = float(overall[k])
        return out

class TransitionScorer:
    """Legacy adapter — preserved for backward compat."""

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        self._eval = TransitionEvaluator(base_weights=weights)

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        return self._eval.evaluate(from_t, to_t, intent=intent, section_context=section_context)

    def score_all_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent] | None = None,
        *,
        section_context: SectionContext | None = None,
    ) -> dict[TransitionIntent, TransitionScore]:
        return self._eval.evaluate_intents(from_t, to_t, intents, section_context=section_context)

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
        *,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        return self._eval.evaluate(
            from_t, to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
            section_context=section_context,
        )
```

- [ ] **Step 3:** Run tests + all golden — green.
- [ ] **Step 4:** Commit.

### Task 4.2: Replace `scorer.py` body with re-export

Replace `app/domain/transition/scorer.py` body:

```python
"""Backward-compat re-export — canonical TransitionScorer lives in orchestrator.py."""

from app.domain.transition.orchestrator import TransitionEvaluator, TransitionScorer
from app.domain.transition.score import TransitionScore

__all__ = ["TransitionEvaluator", "TransitionScore", "TransitionScorer"]
```

Run all tests → green.

Commit + push + PR + memory anchor.

---

# Phase 5 — Recipe Layer (PR 5)

**Branch:** `refactor/transition-arch-v5-recipe`.

**Goal:** Distribute `_recipe_legacy.py` (333 LOC) + `_builders_legacy.py` (374 LOC) into Template Method hierarchy + envelope helpers + factory.

### Task 5.1: Migrate recipe primitives

**Files:**
- Create: `app/domain/transition/recipe/constants.py` — `LEVEL_SILENT`, `LEVEL_UNITY`, `DEFAULT_TRANSITION_BARS`, `MuteFXTrigger`, `Deck`.
- Create: `app/domain/transition/recipe/model.py` — `StemKeyframe`, `MuteFXEvent`, `NeuralMixRecipe` (data only, no JSON methods).
- Create: `app/domain/transition/recipe/serialization.py` — JSON `to_dict`/`from_dict`/`to_json`/`from_json` as free functions; also injected as `NeuralMixRecipe.to_json` methods via monkey-patch in `recipe/__init__.py` for backward compat.
- Create: `app/domain/transition/recipe/api.py` — `KeyframeBundle = tuple[tuple[StemKeyframe, ...], tuple[MuteFXEvent, ...]]`.

Run golden recipe tests — must remain green.

Commit per file.

### Task 5.2: Envelope helpers

**Files:**
- Create: `app/domain/transition/recipe/envelopes/linear_fade.py` — `_crossfade_full(deck, *, fade_in, bars)` helper from `_builders_legacy.py`.
- Create: `app/domain/transition/recipe/envelopes/hold_then_fade.py` — `_hold`, `_ramp` from `_builders_legacy.py`.
- Create: `app/domain/transition/recipe/envelopes/kill_with_echo.py` — sequential-kill+echo logic shared by ECHO_OUT (different from `_cut` because shared bar fractions differ).
- Create: `app/domain/transition/recipe/envelopes/enter_ramp.py` — B-side enter helpers.

Each helper is a pure function; tests assert it returns the expected `tuple[StemKeyframe, ...]` for the same `(bars, …)` inputs as before. Commit.

### Task 5.3: `BaseRecipeBuilder`

**Files:**
- Create: `app/domain/transition/recipe/builders/base.py`

```python
"""BaseRecipeBuilder — Template Method for recipe construction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.recipe.api import KeyframeBundle
from app.domain.transition.recipe.model import MuteFXEvent, StemKeyframe

class BaseRecipeBuilder(ABC):
    transition: ClassVar[NeuralMixTransition]

    def build(self, bars: int) -> KeyframeBundle:
        if bars <= 0:
            raise ValueError(f"bars must be positive, got {bars}")
        a_kfs = self._build_a_envelope(bars)
        b_kfs = self._build_b_envelope(bars)
        fx = self._build_fx_events(bars)
        return tuple(list(a_kfs) + list(b_kfs)), fx

    @abstractmethod
    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]: ...

    @abstractmethod
    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]: ...

    def _build_fx_events(self, bars: int) -> tuple[MuteFXEvent, ...]:
        return ()
```

### Task 5.4-5.10: 7 concrete builders

For each preset, create a file in `recipe/builders/` extending `BaseRecipeBuilder` with the verbatim keyframe layout from `_builders_legacy.py`. Tests: assert each builder's `.build(32)` matches the golden recipe snapshot.

- `FadeRecipeBuilder`: full-stem linear ramps.
- `EchoOutRecipeBuilder`: sequential stem-kill on A + B fade-up; includes 4 MuteFX events.
- `_SustainBuilder` (intermediate ABC, sustained_stem ClassVar) → `VocalSustainRecipeBuilder` / `HarmonicSustainRecipeBuilder`.
- `DrumSwapRecipeBuilder`.
- `_CutBuilder` (intermediate, cut_stem + slam_back ClassVars) → `VocalCutRecipeBuilder` / `DrumCutRecipeBuilder`.

Commit per builder.

### Task 5.11: `RecipeBuilderRegistry` + `build_recipe` factory

```python
# app/domain/transition/recipe/factory.py
"""Factory + registry for recipe builders."""

from collections.abc import Mapping

from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.recipe.api import KeyframeBundle  # noqa
from app.domain.transition.recipe.builders.base import BaseRecipeBuilder
from app.domain.transition.recipe.builders.drum_cut import DrumCutRecipeBuilder
from app.domain.transition.recipe.builders.drum_swap import DrumSwapRecipeBuilder
from app.domain.transition.recipe.builders.echo_out import EchoOutRecipeBuilder
from app.domain.transition.recipe.builders.fade import FadeRecipeBuilder
from app.domain.transition.recipe.builders.harmonic_sustain import HarmonicSustainRecipeBuilder
from app.domain.transition.recipe.builders.vocal_cut import VocalCutRecipeBuilder
from app.domain.transition.recipe.builders.vocal_sustain import VocalSustainRecipeBuilder
from app.domain.transition.recipe.constants import DEFAULT_TRANSITION_BARS
from app.domain.transition.recipe.model import NeuralMixRecipe

DEFAULT_BUILDERS: dict[NeuralMixTransition, BaseRecipeBuilder] = {
    NeuralMixTransition.FADE: FadeRecipeBuilder(),
    NeuralMixTransition.ECHO_OUT: EchoOutRecipeBuilder(),
    NeuralMixTransition.VOCAL_SUSTAIN: VocalSustainRecipeBuilder(),
    NeuralMixTransition.HARMONIC_SUSTAIN: HarmonicSustainRecipeBuilder(),
    NeuralMixTransition.DRUM_SWAP: DrumSwapRecipeBuilder(),
    NeuralMixTransition.VOCAL_CUT: VocalCutRecipeBuilder(),
    NeuralMixTransition.DRUM_CUT: DrumCutRecipeBuilder(),
}

def build_recipe(
    transition: NeuralMixTransition,
    *,
    bars: int = DEFAULT_TRANSITION_BARS,
    builders: Mapping[NeuralMixTransition, BaseRecipeBuilder] | None = None,
    mix_in_section: str | None = None,
    mix_out_section: str | None = None,
    confidence: float = 0.5,
    rescue: NeuralMixTransition = NeuralMixTransition.ECHO_OUT,
    explanation: str = "",
    warnings: tuple[str, ...] = (),
) -> NeuralMixRecipe:
    if bars <= 0:
        raise ValueError(f"bars must be positive, got {bars}")
    registry = builders or DEFAULT_BUILDERS
    builder = registry[transition]
    keyframes, fx_events = builder.build(bars)
    return NeuralMixRecipe(
        transition=transition, bars=bars,
        keyframes=keyframes, fx_events=fx_events,
        mix_in_section=mix_in_section, mix_out_section=mix_out_section,
        confidence=confidence, rescue=rescue,
        explanation=explanation, warnings=warnings,
    )
```

Commit.

### Task 5.12: `build_recipe_for_pair` orchestrator

Move from `_picker_legacy.py:build_recipe_for_pair` to `app/domain/transition/recipe/orchestrator.py`. Reads picker decision and dispatches into `build_recipe`. Update `_picker_legacy.py` to re-export `build_recipe_for_pair` from new location.

Commit.

### Task 5.13: Replace `_builders_legacy.py` / `_recipe_legacy.py` bodies with re-exports

Both files become thin re-exports from the new structure. Run all tests + golden recipe tests → green.

Commit + push + PR titled "refactor(transition): Phase 5 — recipe layer to Template Method + Registry".

Memory anchor.

---

# Phase 6 — Picker (CoR + Proxies) (PR 6)

**Branch:** `refactor/transition-arch-v6-picker`.

**Goal:** Distribute `_picker_legacy.py` into pipeline + 3 proxies + 7 rules.

### Task 6.1: Migrate `PickerDecision` + Protocol

**Files:**
- Create: `app/domain/transition/picker/api.py` — `PickerDecision` frozen dataclass. (Already imported from `api.py` Protocols.)

Commit.

### Task 6.2-6.4: 3 proxies

For each of `SpectralVocalActivityDetector`, `HarmonicMotifDetector`, `CamelotCompatibilityCheck`: copy logic from `_picker_legacy.py:_vocal_active` / `_harmonic_motif` / `_camelot_compatible` into a class implementing the matching Protocol from `api.py`. Tests assert behaviour matches legacy helpers byte-for-byte. Commit per proxy.

### Task 6.5-6.11: 7 rules

For each rule file in `picker/rules/`, implement a `PickerRule` Protocol-compliant class:

| File | Rule | Source in `_picker_legacy.py` |
|---|---|---|
| `hard_reject_rescue.py` | HardRejectRescueRule | `pick_neural_mix` step 1 |
| `drum_only_section.py` | DrumOnlySectionRule | step 2 |
| `vocal_active.py` | VocalActiveRule | step 3 |
| `harmonic_sustain.py` | HarmonicSustainRule | step 4 |
| `energy_drop_to_slam.py` | EnergyDropToSlamRule | step 5 |
| `ambient_or_cooldown.py` | AmbientOrCooldownRule | step 6 |
| `default_echo_out.py` | DefaultEchoOutRule | step 7 |

Each rule's `evaluate(...)` returns either a `PickerDecision` or `None` (defer). Tests: each rule unit-tested for fire/no-fire cases. Commit per rule.

### Task 6.12: `PickerPipeline` + `pick_neural_mix` adapter

```python
# app/domain/transition/picker/pipeline.py
"""CoR pipeline for picker rules."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.transition.api import HarmonicMotifDetector, PickerRule, VocalActivityDetector
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.proxies.harmonic_motif import HarmonicMotifDetector as DefaultHarmonic
from app.domain.transition.picker.proxies.vocal_activity import SpectralVocalActivityDetector
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.shared.features import TrackFeatures

class PickerPipeline:
    def __init__(
        self,
        rules: Sequence[PickerRule],
        *,
        vocal_detector: VocalActivityDetector | None = None,
        harmonic_detector: HarmonicMotifDetector | None = None,
    ) -> None:
        self._rules = tuple(rules)
        self._vocal = vocal_detector or SpectralVocalActivityDetector()
        self._harmonic = harmonic_detector or DefaultHarmonic()

    def pick(
        self,
        score: TransitionScore,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        subgenre_pair: SubgenrePairType | None = None,
        intent: TransitionIntent | None = None,
    ) -> PickerDecision:
        for rule in self._rules:
            decision = rule.evaluate(
                score, from_t, to_t,
                section_context=section_context,
                subgenre_pair=subgenre_pair,
                intent=intent,
            )
            if decision is not None:
                return decision
        # The default_echo_out rule should always fire; fallback for safety:
        from app.domain.transition.enums import NeuralMixTransition
        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=0.5, reason="no rule matched (defensive fallback)",
        )
```

`picker/__init__.py:DEFAULT_RULES` + functional `pick_neural_mix` adapter.

Commit. Run all golden picker tests → green.

### Task 6.13: Replace `_picker_legacy.py` with re-exports

Body becomes:

```python
"""Backward-compat re-export — canonical picker lives in picker/ package."""

from app.domain.transition.picker import PickerDecision, build_recipe_for_pair, pick_neural_mix

__all__ = ["PickerDecision", "build_recipe_for_pair", "pick_neural_mix"]
```

Commit + push + PR + memory anchor.

---

# Phase 7 — Cleanup + DI Switch + Docs (PR 7)

**Branch:** `refactor/transition-arch-v7-cleanup`.

### Task 7.1: DI switch in `app/server/lifespan.py`

- [ ] **Step 1:** Read current import: `from app.domain.transition.scorer import TransitionScorer`. Replace with `from app.domain.transition.orchestrator import TransitionEvaluator`. Update DI registration to expose `TransitionEvaluator` instance under the `TransitionScorerProtocol` slot (it already satisfies the structural contract since `TransitionScorer` is now a thin wrapper around the same `TransitionEvaluator`).
- [ ] **Step 2:** Confirm `app/handlers/transition_persist.py:TransitionScorerProtocol` doesn't need changes — it requires only `.score(...)` which the adapter still provides.
- [ ] **Step 3:** Run full test suite — green. Commit.

### Task 7.2-7.5: OCP acceptance tests

For each Protocol family, write a test demonstrating extension without core edits:

- `tests/domain/transition/test_extension_recipe_builder.py` — synthetic `FilterSweepRecipeBuilder` plugs in via custom `builders` dict to `build_recipe`.
- `tests/domain/transition/test_extension_picker_rule.py` — custom rule prepended to `PickerPipeline(rules=...)`.
- `tests/domain/transition/test_extension_weight_overlay.py` — custom overlay inserted into `CompositeScorer(overlays=...)`.
- `tests/domain/transition/test_extension_scoring_component.py` — custom component added to `CompositeScorer(components=...)`.

Each test ≤ 50 LOC, asserts the extension is invoked. Commit per test.

### Task 7.6: Remove `INTENT_WEIGHT_MODIFIERS` duplicate

If `weights.py` contains `INTENT_WEIGHT_MODIFIERS` (verify by grep), delete it; `intent.py` is the canonical source. Verify all imports point at `intent.py`. Run tests. Commit: `chore(transition): remove duplicate INTENT_WEIGHT_MODIFIERS from weights.py`.

### Task 7.7: Add import-linter contract

Edit `.importlinter` adding the contract from spec section 8.3. Run `lint-imports` → green. Commit: `chore: add import-linter contract for transition subsystem layers`.

### Task 7.8: Update `docs/transition-scoring.md`

- Replace "Module Layout" section with the new directory structure from spec section 4.1.
- Add new section "Extension Points" describing how to add: new `ScoringComponent`, `PickerRule`, `RecipeBuilder`, `WeightOverlay`, `VocalActivityDetector` (each: file path template + 1-line registry edit). Commit.

### Task 7.9: Create `docs/transition-architecture.md`

New doc with: Mermaid dependency diagram, GoF pattern mapping (mirrors spec section 5), example acceptance-test snippet. Commit.

### Task 7.10: Version bump

Edit `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CLAUDE.md` — change `1.4.0` to `1.5.0` in each. Commit: `chore(release): bump version 1.4.0 → 1.5.0`.

### Task 7.11: CHANGELOG entry

Insert under `# Changelog`:

```markdown
## [1.5.0] - 2026-MM-DD

### Changed (internal — no behaviour change)

- **Transition subsystem refactor.** `app/domain/transition/` reorganised under OCP/SOLID/GoF:
  Strategy (`ScoringComponent`, `HardConstraint`, `WeightOverlay`, `PickerRule`,
  `RecipeBuilder`, `VocalActivityDetector`), Composite (`CompositeScorer`),
  Chain of Responsibility (`HardConstraintChain`, `PickerPipeline`),
  Template Method (`BaseRecipeBuilder`), Registry/Factory (explicit module-level
  default lists). 16 files → ~55, ~200 LOC avg → ~50 LOC avg.
- Scalar + bulk scoring co-located per component (`scoring/components/<name>.py`
  exports both `score` and `score_pairs`). `bulk_scorer.py` retained as a thin
  re-export shim.
- Single `TransitionEvaluator.evaluate*` orchestrator replaces the three legacy
  entry points on `TransitionScorer`; the latter remains as a backward-compat
  adapter. ~80 LOC of duplicated `_apply_section_overlay` / `_compute_score`
  eliminated.
- Adding a new scoring component / picker rule / recipe builder / weight overlay
  now requires one new file + one line in `__init__.py` — verified by four
  acceptance tests under `tests/domain/transition/test_extension_*.py`.
- Public API frozen on 21 names (`tests/domain/transition/test_public_api_freeze.py`).
- Behaviour byte-identical: three-level golden snapshot tests (scoring math,
  recipe envelopes, picker decisions) green at 1e-9 / 1e-7 tolerance; bulk
  parity extended to (intent × section_pair_class).
```

Commit.

### Task 7.12: Phase 7 gate + release PR

- [ ] **Step 1:** `make check` green, all golden + acceptance tests green.
- [ ] **Step 2:** Push + open PR titled "release: v1.5.0 — transition architecture refactor".
- [ ] **Step 3:** Memory anchor.

---

# Phase 8 — Release v1.5.0

After PR 7 merge:

- [ ] **Tag:** `git checkout main && git pull --ff-only && git tag -a v1.5.0 -m "v1.5.0" && git push origin v1.5.0`
- [ ] **GitHub Release:** `gh release create v1.5.0 --title "v1.5.0 — transition architecture refactor" --notes-file <(echo "See CHANGELOG.md")`.
- [ ] **Plugin install update** (per user — `claude plugin marketplace update dj-music-plugin && claude plugin update dj-music@dj-music-plugin`).

---

# Appendix A — Memory Anchors

Recorded after each phase merge. Format: `<Phase> | <branch> | <main commit SHA after squash> | <acceptance facts> | <next step>`.

| Phase | Branch | SHA | Facts | Next |
|---|---|---|---|---|
| Pre-flight | (no branch — cherry-pick onto golden branch) | (none) | spec committed, baseline `make check` green, `__all__` == 21 | Phase 0 |
| 0 | refactor/transition-arch-v0-golden | _TBD on merge_ | 56 snapshots, 5 golden test files, 21-name freeze, bulk parity extended | Phase 1 |
| 1 | refactor/transition-arch-v1-protocols | _TBD_ | 8 Protocols, 17 new modules/packages, legacy modules renamed `_*_legacy.py`, re-export shims preserve API | Phase 2 |
| 2 | refactor/transition-arch-v2-constraints | _TBD_ | 3 Specs + Chain, `hard_constraints.py` is adapter | Phase 3 |
| 3 | refactor/transition-arch-v3-scoring | _TBD_ | 6 components scalar+bulk co-located, Composite + 3 Overlays, `bulk_scorer.py` is adapter, `_neural_mix_legacy.py` is shim | Phase 4 |
| 4 | refactor/transition-arch-v4-evaluator | _TBD_ | `TransitionEvaluator`, `TransitionScorer` is adapter, dedup'd 80 LOC | Phase 5 |
| 5 | refactor/transition-arch-v5-recipe | _TBD_ | `BaseRecipeBuilder` + 7 concrete + factory, `_builders_legacy.py` / `_recipe_legacy.py` are shims | Phase 6 |
| 6 | refactor/transition-arch-v6-picker | _TBD_ | `PickerPipeline` + 7 rules + 3 proxies, `_picker_legacy.py` is shim | Phase 7 |
| 7 | refactor/transition-arch-v7-cleanup | _TBD_ | DI switch, 4 OCP acceptance tests, import-linter contract, docs updated, v1.5.0 | Phase 8 (release) |

Fill the SHA column on each PR merge: `git rev-parse main`.

---

# Appendix B — Phase Gates Checklist

Run before opening each PR:

- [ ] `make check` exits 0 (ruff + mypy + import-linter + pytest).
- [ ] `uv run pytest tests/domain/transition/ -q` green.
- [ ] `uv run pytest tests/domain/transition/test_golden_*.py -q` green.
- [ ] `uv run pytest tests/domain/transition/test_bulk_scorer_parity.py -q` green.
- [ ] `uv run pytest tests/domain/transition/test_public_api_freeze.py -q` green.
- [ ] `uv run python -c "import app.domain.transition as m; assert len(m.__all__) == 21"` exits 0.
- [ ] `git status` clean.
- [ ] Branch up-to-date with `main` (`git merge-base --is-ancestor origin/main HEAD`).

---

# Appendix C — Verification Commands Cheat Sheet

| Purpose | Command |
|---|---|
| Quick golden-only check | `uv run pytest tests/domain/transition/test_golden_*.py -q` |
| Quick parity check | `uv run pytest tests/domain/transition/test_bulk_scorer_parity.py -q` |
| Per-file tests | `uv run pytest tests/domain/transition/<sub>/ -q` |
| API surface | `uv run python -c "import app.domain.transition as m; print(sorted(m.__all__))"` |
| Re-generate golden snapshots (deliberate behaviour change) | `REGEN_GOLDEN=1 uv run pytest tests/domain/transition/test_golden_*.py -q` |
| Ruff this layer | `uv run ruff check app/domain/transition/ tests/domain/transition/` |
| Mypy this layer | `uv run mypy app/domain/transition/` |
| Import-linter | `uv run lint-imports` |
| Full `make check` | `make check` |
| Find external consumers | `grep -rn "from app.domain.transition" --include="*.py" app/ tests/` |

---

# Appendix D — Quick reference: spec ↔ task map

| Spec section | Task(s) |
|---|---|
| Section 4.1 (directory structure) | 1.3, all of Phase 3-6 |
| Section 4.2 (public API freeze) | 0.6, 7.x |
| Section 4.4 (Protocols) | 1.2 |
| Section 4.5 (TransitionScorer adapter) | 4.1 |
| Section 5.1 Strategy | 2.x, 3.3-3.8, 6.x |
| Section 5.2 Composite | 3.14 |
| Section 5.3 CoR | 2.5 (constraints), 6.12 (picker) |
| Section 5.4 Template Method | 5.3 |
| Section 5.5 Factory/Registry | 3.15, 5.11 |
| Section 6 acceptance (OCP demo) | 7.2-7.5 |
| Section 7 PR sequence | Phases 0-7 |
| Section 8 Testing strategy | 0.1-0.7 |
| Section 9 Risks | (mitigation embedded in tasks) |
| Section 10 DoD | All phase gates + 7.x |

---

**Plan length:** 8 phases, ~70 tasks, ~250 steps total.

**Execution handoff:** After each phase merge, choose execution mode for the next phase: `superpowers:subagent-driven-development` (fresh subagent per task with review between) or `superpowers:executing-plans` (inline with checkpoints).
