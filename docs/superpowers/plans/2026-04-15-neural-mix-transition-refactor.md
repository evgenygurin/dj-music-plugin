# Neural Mix Transition Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken 12-type legacy transition system with clean 7-FX Neural Mix architecture using `NeuralMixCrossfaderFX` as the sole type, `TransitionSelector` as the selection engine, and a proper module structure.

**Architecture:** `types.py` → `constants.py` → `recipe.py` (dataclasses) → `recipe_decision.py` + `recipe_steps.py` (domain logic, already exist) → `selector.py` (new orchestrator). Delete all legacy files. Update consumers.

**Tech Stack:** Python 3.12, dataclasses, StrEnum/IntEnum, SQLAlchemy 2.0 async, Alembic

---

## Current Broken State (read before starting)

The module is partially broken:
- `app/transition/__init__.py` imports `TransitionRecipe`, `TransitionType` from `recipe.py` — **neither is defined there**. Every import of `app.transition` fails.
- `recipe_engine.py` (686 LOC) uses 12 old `TransitionType` values, all imported from `recipe.py` — **all broken**.
- `recipe_decision.py` + `recipe_steps.py` are the NEW correct approach — both are complete but **currently orphaned (never called)**.
- `subgenre_rules.py` imports `TransitionType` from `recipe.py` — **broken**.
- All transition tests fail with `ImportError`.

---

## File Map

**Create:**
- `app/transition/types.py` — `Stem`, `StemAction`, `SubgenrePairType` (moved from subgenre_rules), `TransitionIntent` (moved from intent.py—keep intent.py, just import from types)
- `app/transition/constants.py` — all numeric constants from `weights.py` (rename, minus `StyleRules`)
- `app/transition/selector.py` — `TransitionSelector` (wraps existing recipe_decision + recipe_steps)

**Rewrite:**
- `app/transition/recipe.py` — `EQPlan` + `TransitionRecipe` + clean `RecipeStep`; `StemAction` imported from `types.py`
- `app/transition/subgenre_rules.py` — remove broken `TransitionType`; import `SubgenrePairType` from `types.py`
- `app/transition/scorer.py` — remove `style.py` imports/re-exports; import from `constants.py`
- `app/transition/__init__.py` — clean public API

**Update imports only (no logic change):**
- `app/transition/components/bpm.py` → `constants` instead of `weights`
- `app/transition/components/energy.py` → same
- `app/transition/components/harmonic.py` → same
- `app/transition/components/spectral.py` → same
- `app/transition/components/groove.py` → same
- `app/transition/components/timbral.py` → same
- `app/transition/recipe_decision.py` → `SubgenrePairType` from `types.py`
- `app/transition/hard_constraints.py` → `constants` instead of `weights`
- `app/services/set/scoring.py` → `TransitionSelector` instead of `recommend_recipe`/`recommend_style`/`style_profile`
- `app/services/set/cheatsheet.py` → same
- `app/db/models/transition.py` → `fx_type` replaces `transition_type`

**Delete:**
- `app/transition/recipe_engine.py` (686 LOC, replaced by `selector.py`)
- `app/transition/style.py` (135 LOC, replaced by `selector.py`)
- `app/transition/neural_mix.py` (499 LOC, orphaned)
- `app/transition/legacy_recipe_map.py` (44 LOC, obsolete)
- `app/transition/weights.py` (153 LOC, renamed to `constants.py`)

**Tests — rewrite/delete:**
- `tests/test_transition/test_recipe_engine.py` → delete (becomes `test_selector.py`)
- `tests/test_transition/test_neural_mix.py` → delete
- `tests/test_transition/test_recipe.py` → update (add EQPlan/TransitionRecipe tests)
- `tests/test_transition/test_subgenre_rules.py` → remove `_PREFERRED_TYPES` tests
- `tests/test_transition/test_recipe_integration.py` → update to use `TransitionSelector`
- `tests/test_domain/test_transition_style.py` → delete (style.py gone)
- `tests/test_domain/test_transition_weights.py` → update to `constants`
- `tests/test_transition/test_selector.py` → new
- `tests/test_services/test_transition_scoring_p2.py` → update selector import

**New migration:**
- `app/db/migrations/versions/<hash>_add_fx_type_drop_transition_type.py`

---

## Task 1: Create `app/transition/types.py`

**Files:**
- Create: `app/transition/types.py`
- Test: `tests/test_transition/test_types.py`

- [ ] **Step 1.1: Write failing test**

```python
# tests/test_transition/test_types.py
from app.transition.types import Stem, StemAction, SubgenrePairType, TransitionIntent

def test_stem_values():
    assert Stem.DRUMS == "drums"
    assert Stem.BASS == "bass"
    assert Stem.HARMONICS == "harmonics"
    assert Stem.VOCALS == "vocals"

def test_stem_action_values():
    assert StemAction.FADE_IN == "fade_in"
    assert StemAction.FADE_OUT == "fade_out"
    assert StemAction.CUT == "cut"
    assert StemAction.SWAP == "swap"
    assert StemAction.MUTE == "mute"
    assert StemAction.SOLO == "solo"

def test_subgenre_pair_type_values():
    assert SubgenrePairType.AMBIENT_PAIR == "ambient_pair"
    assert SubgenrePairType.HARD_PAIR == "hard_pair"
    assert SubgenrePairType.MIXED_PAIR == "mixed_pair"

def test_transition_intent_ordering():
    assert TransitionIntent.MAINTAIN < TransitionIntent.RAMP_UP
    assert TransitionIntent.RAMP_UP < TransitionIntent.COOL_DOWN
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_transition/test_types.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.transition.types'`

- [ ] **Step 1.3: Create `app/transition/types.py`**

```python
"""Shared enums for the transition subsystem.

Single source of truth for all transition-related enum types.
Imported by recipe.py, subgenre_rules.py, selector.py, and consumers.
No dependencies on other app.transition modules.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

class Stem(StrEnum):
    """djay Pro AI Neural Mix stem lanes."""

    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"

class StemAction(StrEnum):
    """Automation action applied to a stem lane."""

    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"

class SubgenrePairType(StrEnum):
    """Techno subgenre classification for a track pair."""

    AMBIENT_PAIR = "ambient_pair"
    HARD_PAIR = "hard_pair"
    ACID_PAIR = "acid_pair"
    MELODIC_PAIR = "melodic_pair"
    HYPNOTIC_PAIR = "hypnotic_pair"
    MIXED_PAIR = "mixed_pair"

class TransitionIntent(IntEnum):
    """Context-aware intent for the transition (set position + energy arc)."""

    MAINTAIN = 0
    RAMP_UP = 1
    COOL_DOWN = 2
    CONTRAST = 3
```

- [ ] **Step 1.4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_transition/test_types.py -v
```
Expected: 4 tests PASS

- [ ] **Step 1.5: Update `app/transition/intent.py` to import `TransitionIntent` from `types.py`**

`intent.py` currently defines `TransitionIntent` itself. With `types.py` existing, there would be two definitions — different Python objects despite same values. Fix: make `intent.py` import from `types.py`.

In `app/transition/intent.py`:
```python
# Remove the existing TransitionIntent class definition.
# Add at the top of imports:
from app.transition.types import TransitionIntent  # re-export

# Keep INTENT_WEIGHT_MODIFIERS and infer_intent() unchanged.
# Add to __all__ if present:
__all__ = ["TransitionIntent", "INTENT_WEIGHT_MODIFIERS", "infer_intent"]
```

After this change, all existing consumers (`scorer.py`, `optimization/fitness.py`, `recipe_decision.py`) that import `TransitionIntent` from `intent.py` still work — `intent.py` now re-exports it.

Verify:
```bash
.venv/bin/python -c "from app.transition.intent import TransitionIntent, infer_intent; from app.transition.types import TransitionIntent as T2; assert TransitionIntent is T2; print('same object OK')"
```
Expected: `same object OK`

- [ ] **Step 1.6: Commit**

```bash
git add app/transition/types.py tests/test_transition/test_types.py
git commit -F /tmp/msg.txt  # write msg first
```

Commit message (`/tmp/msg.txt`):
```bash
feat(transition): add types.py — canonical Stem/StemAction/SubgenrePairType/TransitionIntent enums

Foundation layer for Neural Mix refactor. No other modules changed yet.
```

---

## Task 2: Create `app/transition/constants.py` (from `weights.py`)

**Files:**
- Create: `app/transition/constants.py`
- Modify: `app/transition/components/bpm.py`, `energy.py`, `harmonic.py`, `spectral.py`, `groove.py`, `timbral.py`
- Modify: `app/transition/hard_constraints.py`, `app/transition/scorer.py`
- Delete: `app/transition/weights.py`
- Test: `tests/test_domain/test_transition_weights.py`

- [ ] **Step 2.1: Create `app/transition/constants.py`**

```python
"""All transition scoring constants — the only place for magic numbers.

Pure data: no I/O, no logic, no imports from other app.transition modules.
Components and scorer import from here; settings.py handles runtime-configurable
thresholds (recipe decision tree uses settings.*).
"""

from __future__ import annotations

from app.core.constants import DEFAULT_TRANSITION_WEIGHTS

# ── Component weights (sum = 1.0) ────────────────────────────────────────────
# Single source of truth lives in app/core/constants.py so the core layer
# doesn't depend on the domain layer. Re-exported here for ergonomic imports.
DEFAULT_WEIGHTS: dict[str, float] = DEFAULT_TRANSITION_WEIGHTS

# ── BPM scoring ──────────────────────────────────────────────────────────────
BPM_GAUSS_SIGMA: float = 6.0          # ~4.8% on 124 BPM
BPM_STABILITY_FLOOR: float = 0.7      # max 30% penalty for unstable tempo
BPM_CONFIDENCE_PENALTY_FLOOR: float = 0.7

# ── Harmonic scoring ─────────────────────────────────────────────────────────
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
ATONAL_RELAX_FLOOR: float = 0.8        # both atonal → floor 0.8
HNR_NORM_LOW_DB: float = -30.0         # HNR < -30 → factor 0.5
HNR_NORM_HIGH_DB: float = 0.0          # HNR ≥ 0 → factor 1.0
HNR_NORM_FLOOR: float = 0.5
TONNETZ_BLEND: float = 0.30            # weight of tonnetz cosine vs Camelot base
KEY_CONFIDENCE_BLEND_THRESHOLD: float = 0.5

# ── Energy scoring ───────────────────────────────────────────────────────────
ENERGY_SIGMOID_DIVISOR: float = 3.0
LRA_DIFF_PENALTY_THRESHOLD: float = 5.0
LRA_DIFF_PENALTY: float = 0.10
CREST_DIFF_PENALTY_THRESHOLD: float = 4.0
CREST_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Spectral scoring ─────────────────────────────────────────────────────────
SPECTRAL_SUB_WEIGHTS: dict[str, float] = {
    "mfcc": 0.45,         # #1 predictor of real DJ transitions (Kim ISMIR 2020)
    "centroid": 0.15,
    "energy_bands": 0.15,
    "rolloff": 0.10,
    "slope": 0.10,
    "flux": 0.05,
}
DISSONANCE_PAIR_THRESHOLD: float = 0.4
DISSONANCE_PENALTY: float = 0.15
COMPLEXITY_DIFF_THRESHOLD: float = 10.0
COMPLEXITY_PENALTY: float = 0.10

# ── Groove scoring ───────────────────────────────────────────────────────────
GROOVE_SUB_WEIGHTS: dict[str, float] = {
    "onset_rate": 0.25,
    "kick_prominence": 0.25,
    "beat_loudness": 0.20,
    "pulse_clarity": 0.10,
    "hp_ratio": 0.10,
    "tempogram": 0.10,
}

# ── Timbral scoring ──────────────────────────────────────────────────────────
TIMBRAL_SPECTRAL_CONTRAST_NORM: float = 15.0   # dB
TIMBRAL_PITCH_SALIENCE_NORM: float = 0.5
TIMBRAL_DANCEABILITY_NORM: float = 3.0
TIMBRAL_DYNAMIC_COMPLEXITY_NORM: float = 10.0
TIMBRAL_SUB_WEIGHTS: dict[str, float] = {
    "spectral_contrast": 0.35,
    "pitch_salience": 0.35,
    "danceability": 0.15,
    "dynamic_complexity": 0.15,
}

# ── Section-aware modifiers ───────────────────────────────────────────────────
# When both mix windows fall on percussion-only sections, key compatibility
# loses perceptual relevance (Pioneer DJ blog; Vande Veire & De Bie 2018).
DRUM_ONLY_HARMONIC_FLOOR: float = 0.85
DRUM_ONLY_WEIGHT_OVERRIDE: dict[str, float] = {
    "bpm": 0.22,
    "harmonic": 0.05,
    "energy": 0.18,
    "spectral": 0.20,
    "groove": 0.20,
    "timbral": 0.15,
}

# ── Conflict detection (Mosaikbox 2024) ──────────────────────────────────────
GROOVE_CONFLICT_THRESHOLD: float = 0.95
VOCAL_PITCH_SALIENCE_THRESHOLD: float = 0.4
VOCAL_SPECTRAL_CENTROID_FLOOR_HZ: float = 2500.0
VOCAL_OVERLAP_THRESHOLD_MS: float = 2000.0

# ── Audio engineering constants (Allen & Heath / Pioneer) ────────────────────
BASS_SWAP_RAMP_MS: float = 0.0         # hard cut on downbeat — no simultaneous kicks
MICRO_RAMP_MS: float = 5.0             # click prevention (~220 samples @ 44.1kHz)
HPF_FILTER_ORDER: int = 4              # 24 dB/oct (LR4), matches Pioneer DJM-900NXS2
KICK_KILL_CUTOFF_HZ: float = 150.0    # removes kick fundamental + body
```

- [ ] **Step 2.2: Update imports in 6 component files**

In each file, replace `from app.transition.weights import` with `from app.transition.constants import`. The imported names stay the same.

Files to update (sed-style — do each manually with Edit tool):

`app/transition/components/bpm.py`:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

`app/transition/components/energy.py`:
```python
# OLD
from app.transition.weights import ENERGY_SIGMOID_DIVISOR
# NEW
from app.transition.constants import ENERGY_SIGMOID_DIVISOR
```

`app/transition/components/harmonic.py`:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

`app/transition/components/spectral.py`:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

`app/transition/components/groove.py`:
```python
# OLD
from app.transition.weights import GROOVE_SUB_WEIGHTS
# NEW
from app.transition.constants import GROOVE_SUB_WEIGHTS
```

`app/transition/components/timbral.py`:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

`app/transition/hard_constraints.py`:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

- [ ] **Step 2.3: Update `tests/test_domain/test_transition_weights.py`**

Replace the import line:
```python
# OLD
from app.transition.weights import (
# NEW
from app.transition.constants import (
```

- [ ] **Step 2.4: Delete `weights.py`**

```bash
rm app/transition/weights.py
```

- [ ] **Step 2.5: Verify components still import correctly**

```bash
.venv/bin/python -c "from app.transition.components import score_bpm, score_energy, score_harmonic, score_spectral, score_groove, score_timbral; print('OK')"
```
Expected: `OK`

- [ ] **Step 2.6: Run constants tests**

```bash
.venv/bin/python -m pytest tests/test_domain/test_transition_weights.py -v
```
Expected: all PASS

- [ ] **Step 2.7: Commit**

```sql
feat(transition): rename weights.py → constants.py; update all component imports
```

---

## Task 3: Rewrite `app/transition/recipe.py`

**Files:**
- Modify: `app/transition/recipe.py`
- Test: `tests/test_transition/test_recipe.py`

The current `recipe.py` (142 lines) only has `RecipeStep` + broken `StemAction`. Missing: `EQPlan`, `TransitionRecipe`. These must be added. `StemAction` must be removed (now in `types.py`).

- [ ] **Step 3.1: Write the new `recipe.py`**

Replace the entire file:

```python
"""Transition recipe dataclasses — result types produced by TransitionSelector.

EQPlan, RecipeStep, and TransitionRecipe are frozen dataclasses. They are
serialised to JSON and stored in transitions.transition_recipe_json.
StemAction lives in types.py to break the forward-reference cycle.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Literal

from app.core.constants import NeuralMixCrossfaderFX
from app.transition.types import StemAction

@dataclasses.dataclass(frozen=True)
class EQPlan:
    """High-level EQ automation strategy for a transition."""

    low: str = "stem"    # e.g. "stem", "cut", "swap@bar8", "echo_bus"
    mid: str = "stem"
    high: str = "stem"

    def to_dict(self) -> dict[str, str]:
        return {"low": self.low, "mid": self.mid, "high": self.high}

    @classmethod
    def from_dict(cls, data: object) -> EQPlan:
        if not isinstance(data, dict):
            return cls()
        return cls(
            low=data.get("low", "stem") if isinstance(data.get("low"), str) else "stem",
            mid=data.get("mid", "stem") if isinstance(data.get("mid"), str) else "stem",
            high=data.get("high", "stem") if isinstance(data.get("high"), str) else "stem",
        )

def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else None

@dataclasses.dataclass(frozen=True)
class RecipeStep:
    """One bar-timed automation event in a transition playbook."""

    bar: int
    deck: Literal["A", "B", "both"]
    action: str
    stem: str | None = None
    stem_action: StemAction | None = None
    eq_band: str | None = None
    eq_value: float | None = None
    effect: str | None = None
    effect_param: float | None = None

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"bar": self.bar, "deck": self.deck, "action": self.action}
        if self.stem is not None:
            d["stem"] = self.stem
        if self.stem_action is not None:
            d["stem_action"] = str(self.stem_action)
        if self.eq_band is not None:
            d["eq_band"] = self.eq_band
        if self.eq_value is not None:
            d["eq_value"] = self.eq_value
        if self.effect is not None:
            d["effect"] = self.effect
        if self.effect_param is not None:
            d["effect_param"] = self.effect_param
        return d

    @classmethod
    def from_dict(cls, data: object) -> RecipeStep | None:
        if not isinstance(data, dict):
            return None
        bar = _coerce_int(data.get("bar"))
        deck = data.get("deck")
        action = data.get("action")
        if bar is None or not isinstance(deck, str) or deck not in {"A", "B", "both"}:
            return None
        if not isinstance(action, str):
            return None
        stem = _coerce_optional_str(data.get("stem"))
        eq_band = _coerce_optional_str(data.get("eq_band"))
        effect = _coerce_optional_str(data.get("effect"))
        stem_action: StemAction | None = None
        stem_action_raw = data.get("stem_action")
        if stem_action_raw is not None:
            if not isinstance(stem_action_raw, str):
                return None
            try:
                stem_action = StemAction(stem_action_raw)
            except ValueError:
                return None
        eq_value = _coerce_float(data.get("eq_value")) if data.get("eq_value") is not None else None
        effect_param = (
            _coerce_float(data.get("effect_param")) if data.get("effect_param") is not None else None
        )
        return cls(
            bar=bar,
            deck=deck,  # type: ignore[arg-type]
            action=action,
            stem=stem,
            stem_action=stem_action,
            eq_band=eq_band,
            eq_value=eq_value,
            effect=effect,
            effect_param=effect_param,
        )

@dataclasses.dataclass(frozen=True)
class TransitionRecipe:
    """Complete transition playbook returned by TransitionSelector.

    ``fx_type`` is the djay Pro AI Neural Mix Crossfader FX preset.
    ``steps`` is the bar-by-bar stem/EQ automation sequence.
    Serialised to JSON and stored in transitions.transition_recipe_json.
    """

    fx_type: NeuralMixCrossfaderFX | None = None
    bars: int = 16
    steps: tuple[RecipeStep, ...] = ()
    eq_plan: EQPlan = dataclasses.field(default_factory=EQPlan)
    djay_tempo_adjust: str = "none"
    mix_in_section: str | None = None
    mix_out_section: str | None = None
    phrase_align: bool = True
    warnings: tuple[str, ...] = ()
    confidence: float = 0.75
    subgenre_modifier: str | None = None
    rescue_move: str = "adjust blend length to taste"

    def to_json(self) -> str:
        data: dict[str, object] = {
            "fx_type": str(self.fx_type) if self.fx_type else None,
            "bars": self.bars,
            "steps": [s.to_dict() for s in self.steps],
            "eq_plan": self.eq_plan.to_dict(),
            "djay_tempo_adjust": self.djay_tempo_adjust,
            "mix_in_section": self.mix_in_section,
            "mix_out_section": self.mix_out_section,
            "phrase_align": self.phrase_align,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "subgenre_modifier": self.subgenre_modifier,
            "rescue_move": self.rescue_move,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str | None) -> TransitionRecipe | None:
        """Deserialise from DB JSON. Returns None on invalid input."""
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        fx_type: NeuralMixCrossfaderFX | None = None
        fx_raw = data.get("fx_type")
        if isinstance(fx_raw, str):
            try:
                fx_type = NeuralMixCrossfaderFX(fx_raw)
            except ValueError:
                pass  # legacy value — gracefully ignored

        steps_raw = data.get("steps", [])
        steps: tuple[RecipeStep, ...] = ()
        if isinstance(steps_raw, list):
            steps = tuple(s for raw_s in steps_raw if (s := RecipeStep.from_dict(raw_s)) is not None)

        return cls(
            fx_type=fx_type,
            bars=_coerce_int(data.get("bars")) or 16,
            steps=steps,
            eq_plan=EQPlan.from_dict(data.get("eq_plan")),
            djay_tempo_adjust=data.get("djay_tempo_adjust", "none") or "none",
            mix_in_section=_coerce_optional_str(data.get("mix_in_section")),
            mix_out_section=_coerce_optional_str(data.get("mix_out_section")),
            phrase_align=bool(data.get("phrase_align", True)),
            warnings=tuple(w for w in data.get("warnings", []) if isinstance(w, str)),
            confidence=_coerce_float(data.get("confidence")) or 0.75,
            subgenre_modifier=_coerce_optional_str(data.get("subgenre_modifier")),
            rescue_move=data.get("rescue_move", "adjust blend length to taste") or "adjust blend length to taste",
        )
```

- [ ] **Step 3.2: Update `recipe_steps.py` to import `StemAction` from `types.py`**

```python
# In app/transition/recipe_steps.py, line 10:
# OLD
from app.transition.recipe import EQPlan, RecipeStep, StemAction
# NEW
from app.transition.recipe import EQPlan, RecipeStep
from app.transition.types import StemAction
```

- [ ] **Step 3.3: Verify recipe + recipe_steps imports**

```bash
.venv/bin/python -c "from app.transition.recipe import EQPlan, RecipeStep, TransitionRecipe; from app.transition.recipe_steps import build_steps_for_fx; print('OK')"
```
Expected: `OK`

- [ ] **Step 3.4: Update `tests/test_transition/test_recipe.py`**

The test currently imports `DjayTransition`, `TransitionType` which no longer exist. Replace the entire test file:

```python
# tests/test_transition/test_recipe.py
"""Tests for EQPlan, RecipeStep, and TransitionRecipe."""

from app.core.constants import NeuralMixCrossfaderFX
from app.transition.recipe import EQPlan, RecipeStep, TransitionRecipe
from app.transition.types import StemAction

def test_eq_plan_defaults():
    plan = EQPlan()
    assert plan.low == "stem"
    assert plan.mid == "stem"
    assert plan.high == "stem"

def test_eq_plan_round_trip():
    plan = EQPlan(low="cut", mid="filter", high="stem")
    assert EQPlan.from_dict(plan.to_dict()) == plan

def test_recipe_step_round_trip():
    step = RecipeStep(
        bar=4,
        deck="A",
        action="fade out drums",
        stem="drums",
        stem_action=StemAction.FADE_OUT,
    )
    d = step.to_dict()
    restored = RecipeStep.from_dict(d)
    assert restored == step

def test_recipe_step_from_dict_invalid_deck():
    assert RecipeStep.from_dict({"bar": 0, "deck": "C", "action": "x"}) is None

def test_recipe_step_from_dict_bool_bar():
    # bool should not coerce to int
    assert RecipeStep.from_dict({"bar": True, "deck": "A", "action": "x"}) is None

def test_transition_recipe_round_trip():
    step = RecipeStep(bar=0, deck="B", action="bring in B drums", stem="drums", stem_action=StemAction.FADE_IN)
    recipe = TransitionRecipe(
        fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
        bars=16,
        steps=(step,),
        warnings=("key clash",),
        confidence=0.85,
        rescue_move="hard cut if stems clash",
    )
    json_str = recipe.to_json()
    restored = TransitionRecipe.from_json(json_str)
    assert restored is not None
    assert restored.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP
    assert restored.bars == 16
    assert len(restored.steps) == 1
    assert restored.steps[0].stem_action == StemAction.FADE_IN
    assert restored.confidence == 0.85

def test_transition_recipe_from_json_legacy_fx_type():
    """Legacy fx_type values (e.g. old TransitionType strings) are silently ignored."""
    import json
    raw = json.dumps({"fx_type": "BASS_SWAP_SHORT", "bars": 8, "steps": []})
    recipe = TransitionRecipe.from_json(raw)
    assert recipe is not None
    assert recipe.fx_type is None  # not a valid NeuralMixCrossfaderFX value

def test_transition_recipe_from_json_none():
    assert TransitionRecipe.from_json(None) is None

def test_transition_recipe_from_json_invalid():
    assert TransitionRecipe.from_json("not-json") is None
```

- [ ] **Step 3.5: Run recipe tests**

```bash
.venv/bin/python -m pytest tests/test_transition/test_recipe.py -v
```
Expected: all PASS

- [ ] **Step 3.6: Commit**

```text
refactor(transition): rewrite recipe.py — add EQPlan + TransitionRecipe, fix StemAction duplication

TransitionRecipe uses fx_type: NeuralMixCrossfaderFX instead of legacy
TransitionType. from_json gracefully ignores unknown fx_type values.
```

---

## Task 4: Fix `app/transition/subgenre_rules.py`

**Files:**
- Modify: `app/transition/subgenre_rules.py`
- Modify: `tests/test_transition/test_subgenre_rules.py`

Remove the broken `TransitionType` import and the `_PREFERRED_TYPES` / `preferred_type_for_pair` that use it.

- [ ] **Step 4.1: Rewrite `subgenre_rules.py`**

```python
"""Subgenre-specific transition rules — pair classification and bar clamping.

``SubgenrePairType`` lives in ``types.py``; this module provides the
classification and clamping functions used by ``recipe_decision.py``
and ``selector.py``.
"""

from __future__ import annotations

from app.core.constants import TechnoSubgenre
from app.transition.types import SubgenrePairType

_AMBIENT = frozenset({TechnoSubgenre.AMBIENT_DUB, TechnoSubgenre.DUB_TECHNO})
_HARD = frozenset({TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO, TechnoSubgenre.RAW})
_MELODIC = frozenset(
    {TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE, TechnoSubgenre.DETROIT}
)
_HYPNOTIC = frozenset({TechnoSubgenre.HYPNOTIC, TechnoSubgenre.MINIMAL})

def classify_pair(
    mood_a: TechnoSubgenre | str | None,
    mood_b: TechnoSubgenre | str | None,
) -> SubgenrePairType:
    """Classify a track pair by combined subgenre context."""
    if mood_a is None or mood_b is None:
        return SubgenrePairType.MIXED_PAIR
    try:
        a = TechnoSubgenre(mood_a) if isinstance(mood_a, str) else mood_a
    except ValueError:
        return SubgenrePairType.MIXED_PAIR
    try:
        b = TechnoSubgenre(mood_b) if isinstance(mood_b, str) else mood_b
    except ValueError:
        return SubgenrePairType.MIXED_PAIR
    if a in _AMBIENT and b in _AMBIENT:
        return SubgenrePairType.AMBIENT_PAIR
    if a in _HARD and b in _HARD:
        return SubgenrePairType.HARD_PAIR
    if a == TechnoSubgenre.ACID or b == TechnoSubgenre.ACID:
        return SubgenrePairType.ACID_PAIR
    if a in _MELODIC and b in _MELODIC:
        return SubgenrePairType.MELODIC_PAIR
    if a in _HYPNOTIC and b in _HYPNOTIC:
        return SubgenrePairType.HYPNOTIC_PAIR
    return SubgenrePairType.MIXED_PAIR

# Bar clamps per subgenre pair (Kim ISMIR 2020, Mosaikbox 2024, professional DJ practice).
_BAR_CLAMPS: dict[SubgenrePairType, tuple[int, int]] = {
    SubgenrePairType.AMBIENT_PAIR: (32, 64),
    SubgenrePairType.HARD_PAIR: (4, 16),
    SubgenrePairType.HYPNOTIC_PAIR: (16, 32),
    SubgenrePairType.ACID_PAIR: (8, 32),
    SubgenrePairType.MELODIC_PAIR: (16, 48),
    SubgenrePairType.MIXED_PAIR: (8, 48),
}

def clamp_bars(bars: int, pair_type: SubgenrePairType) -> int:
    """Clamp transition bar count to subgenre-appropriate range."""
    lo, hi = _BAR_CLAMPS.get(pair_type, (0, 64))
    return max(lo, min(bars, hi))
```

- [ ] **Step 4.2: Update `recipe_decision.py` import**

In `app/transition/recipe_decision.py`, the import `from app.transition.subgenre_rules import SubgenrePairType, clamp_bars, classify_pair` still works because `SubgenrePairType` is re-exported from the same module. But since `SubgenrePairType` now lives in `types.py`, we should import it directly:

```python
# In app/transition/recipe_decision.py, line 15:
# OLD
from app.transition.subgenre_rules import SubgenrePairType, clamp_bars, classify_pair
# NEW
from app.transition.subgenre_rules import clamp_bars, classify_pair
from app.transition.types import SubgenrePairType
```

- [ ] **Step 4.3: Update `tests/test_transition/test_subgenre_rules.py`**

Remove tests that imported `preferred_type_for_pair` or `_PREFERRED_TYPES`. Keep `classify_pair` and `clamp_bars` tests. Also fix `SubgenrePairType` import:

```python
# OLD
from app.transition.subgenre_rules import SubgenrePairType, classify_pair, clamp_bars
# NEW
from app.transition.subgenre_rules import classify_pair, clamp_bars
from app.transition.types import SubgenrePairType
```

Remove any test that calls `preferred_type_for_pair()`.

- [ ] **Step 4.4: Verify imports**

```bash
.venv/bin/python -c "from app.transition.subgenre_rules import classify_pair, clamp_bars; from app.transition.types import SubgenrePairType; print('OK')"
```

- [ ] **Step 4.5: Run subgenre tests**

```bash
.venv/bin/python -m pytest tests/test_transition/test_subgenre_rules.py -v
```
Expected: all PASS (test count reduced — `preferred_type_for_pair` tests removed)

- [ ] **Step 4.6: Commit**

```text
fix(transition): subgenre_rules.py — remove broken TransitionType dependency

Remove _PREFERRED_TYPES and preferred_type_for_pair (used undefined
TransitionType). SubgenrePairType now imported from types.py.
```

---

## Task 5: Create `app/transition/selector.py`

**Files:**
- Create: `app/transition/selector.py`
- Test: `tests/test_transition/test_selector.py`

`TransitionSelector` is the new `recommend_recipe()`. It wraps the already-correct `recipe_decision.decide_crossfader_fx_and_bars` + `recipe_steps.build_steps_for_fx`.

- [ ] **Step 5.1: Write failing tests**

```python
# tests/test_transition/test_selector.py
"""Tests for TransitionSelector — the new transition FX selection engine."""
import pytest

from app.core.constants import NeuralMixCrossfaderFX, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.core.constants import SectionType
from app.transition.selector import TransitionSelector
from app.transition.types import TransitionIntent

def _score(**kwargs: float) -> TransitionScore:
    defaults = dict(bpm=0.8, harmonic=0.8, energy=0.8, spectral=0.8, groove=0.8, timbral=0.8, overall=0.8)
    defaults.update(kwargs)
    return TransitionScore(**defaults)

def _features(**kwargs: object) -> TrackFeatures:
    return TrackFeatures(bpm=128.0, integrated_lufs=-10.0, **kwargs)  # type: ignore[arg-type]

def test_select_returns_neural_mix_fx():
    selector = TransitionSelector()
    score = _score()
    fx = selector.select(score, _features(), _features())
    assert isinstance(fx, NeuralMixCrossfaderFX)

def test_hard_reject_returns_fade():
    selector = TransitionSelector()
    score = TransitionScore(hard_reject=True, reject_reason="bpm too different")
    fx = selector.select(score, _features(), _features())
    assert fx == NeuralMixCrossfaderFX.NEURAL_MIX_FADE

def test_drum_only_high_groove_returns_drum_cut():
    selector = TransitionSelector()
    score = _score(groove=0.95, overall=0.9)
    ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.OUTRO)
    fx = selector.select(score, _features(), _features(), section_context=ctx)
    assert fx == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT

def test_build_recipe_returns_transition_recipe():
    selector = TransitionSelector()
    score = _score()
    recipe = selector.build_recipe(score, _features(), _features())
    assert isinstance(recipe, TransitionRecipe)
    assert recipe.fx_type is not None
    assert recipe.bars > 0
    assert len(recipe.steps) > 0

def test_build_recipe_bpm_warning():
    selector = TransitionSelector()
    score = _score()
    fa = TrackFeatures(bpm=128.0, integrated_lufs=-10.0)
    fb = TrackFeatures(bpm=133.0, integrated_lufs=-10.0)
    recipe = selector.build_recipe(score, fa, fb)
    assert any("BPM" in w or "bpm" in w.lower() for w in recipe.warnings)

def test_all_seven_fx_are_reachable():
    """Every NeuralMixCrossfaderFX value must be returnable by selector."""
    from app.transition.recipe_steps import build_steps_for_fx
    from app.core.constants import NeuralMixCrossfaderFX
    for fx in NeuralMixCrossfaderFX:
        steps, eq = build_steps_for_fx(fx, 16)
        assert len(steps) > 0, f"{fx} produced no steps"
```

- [ ] **Step 5.2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_transition/test_selector.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.transition.selector'`

- [ ] **Step 5.3: Create `app/transition/selector.py`**

```python
"""TransitionSelector — orchestrates FX selection and recipe building.

Wraps ``recipe_decision.decide_crossfader_fx_and_bars`` (decides which of the
7 Neural Mix FX to use) and ``recipe_steps.build_steps_for_fx`` (generates
the bar-by-bar stem/EQ playbook for that FX).

This replaces ``style.py:recommend_recipe``, ``recipe_engine.py``, and the
dead pathway through ``TransitionRecipeEngine``.
"""

from __future__ import annotations

from app.core.constants import NeuralMixCrossfaderFX, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import EQPlan, TransitionRecipe
from app.transition.recipe_decision import (
    clamp_pair_bars,
    decide_crossfader_fx_and_bars,
    rescue_hint,
    resolve_pair_type,
    snap_bars_to_phrase,
)
from app.transition.recipe_steps import build_steps_for_fx
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.types import SubgenrePairType, TransitionIntent

class TransitionSelector:
    """Select the best Neural Mix Crossfader FX and build a full recipe.

    Usage::

        selector = TransitionSelector()
        recipe = selector.build_recipe(score, features_a, features_b)

    ``select()`` returns the ``NeuralMixCrossfaderFX`` value only.
    ``build_recipe()`` returns a full ``TransitionRecipe`` with steps.
    """

    def select(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        mood_a: TechnoSubgenre | None = None,
        mood_b: TechnoSubgenre | None = None,
        intent: TransitionIntent | None = None,
    ) -> NeuralMixCrossfaderFX:
        """Return the most appropriate Neural Mix FX for this transition."""
        pair_type = resolve_pair_type(features_a, features_b, mood_a, mood_b)
        fx, _bars, _conf, _warnings = decide_crossfader_fx_and_bars(
            score,
            features_a,
            features_b,
            section_context=section_context,
            pair_type=pair_type,
            intent=intent,
        )
        return fx

    def build_recipe(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        mood_a: TechnoSubgenre | None = None,
        mood_b: TechnoSubgenre | None = None,
        intent: TransitionIntent | None = None,
    ) -> TransitionRecipe:
        """Return a full recipe: FX, bar count, step sequence, and metadata."""
        pair_type = resolve_pair_type(features_a, features_b, mood_a, mood_b)

        fx, raw_bars, confidence, extra_warnings = decide_crossfader_fx_and_bars(
            score,
            features_a,
            features_b,
            section_context=section_context,
            pair_type=pair_type,
            intent=intent,
        )

        # Clamp to subgenre range, then snap to musical phrase boundary.
        bars = snap_bars_to_phrase(clamp_pair_bars(raw_bars, pair_type))

        # Build stem/EQ steps for this FX.
        steps, eq_plan = build_steps_for_fx(fx, bars)

        # Warnings.
        warnings: list[str] = list(extra_warnings)
        bpm_a = features_a.bpm or 0.0
        bpm_b = features_b.bpm or 0.0
        bpm_delta = abs(bpm_a - bpm_b)
        if bpm_delta > 4.0:
            warnings.append(f"BPM delta {bpm_delta:.1f} — use sync_lock")
        elif bpm_delta > 1.0:
            warnings.append(f"BPM delta {bpm_delta:.1f} — gradual nudge")

        # Section labels for cheat sheet display.
        mix_out: str | None = None
        mix_in: str | None = None
        if section_context:
            if section_context.from_section is not None:
                mix_out = section_context.from_section.name.lower()
            if section_context.to_section is not None:
                mix_in = section_context.to_section.name.lower()

        return TransitionRecipe(
            fx_type=fx,
            bars=bars,
            steps=steps,
            eq_plan=eq_plan,
            djay_tempo_adjust="sync_lock" if bpm_delta >= 4.0 else ("gradual" if bpm_delta >= 1.0 else "none"),
            mix_in_section=mix_in,
            mix_out_section=mix_out,
            phrase_align=bars > 0,
            warnings=tuple(warnings),
            confidence=confidence,
            subgenre_modifier=pair_type.value if pair_type != SubgenrePairType.MIXED_PAIR else None,
            rescue_move=rescue_hint(fx),
        )
```

- [ ] **Step 5.4: Run selector tests**

```bash
.venv/bin/python -m pytest tests/test_transition/test_selector.py -v
```
Expected: all PASS

- [ ] **Step 5.5: Commit**

```text
feat(transition): add selector.py — TransitionSelector replaces recommend_recipe

Wraps recipe_decision + recipe_steps into a clean class interface.
Replaces the broken TransitionRecipeEngine + style.recommend_recipe pathway.
```

---

## Task 6: Update `app/transition/scorer.py` and `app/transition/__init__.py`

**Files:**
- Modify: `app/transition/scorer.py`
- Modify: `app/transition/__init__.py`

Remove all `style.py` dependencies from `scorer.py`. Fix `__init__.py` to export the new public API.

- [ ] **Step 6.1: Update `scorer.py`**

In `scorer.py`, find and remove:
1. `from app.transition.style import recommend_style, style_profile` (line ~29)
2. `from app.transition.weights import DRUM_ONLY_WEIGHT_OVERRIDE` → change to `from app.transition.constants import DRUM_ONLY_WEIGHT_OVERRIDE`
3. Remove `recommend_style` and `style_profile` from `__all__`

The updated imports section of `scorer.py`:

```python
from app.core.constants import DEFAULT_TRANSITION_WEIGHTS, SectionType
from app.entities.audio.features import TrackFeatures
from app.transition.components import (
    score_bpm,
    score_energy,
    score_groove,
    score_harmonic,
    score_spectral,
    score_timbral,
)
from app.transition.constants import DRUM_ONLY_WEIGHT_OVERRIDE
from app.transition.hard_constraints import check_hard_constraints
from app.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext

__all__ = [
    "TransitionScore",
    "TransitionScorer",
]
```

- [ ] **Step 6.2: Rewrite `app/transition/__init__.py`**

```python
"""Public API for the app.transition package.

Import from here rather than from submodules to stay insulated from
internal reorganisation.
"""

from app.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.transition.recipe import EQPlan, RecipeStep, TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.scorer import TransitionScorer
from app.transition.section_context import SectionContext
from app.transition.selector import TransitionSelector
from app.transition.types import Stem, StemAction, SubgenrePairType, TransitionIntent

__all__ = [
    "EQPlan",
    "RecipeStep",
    "TransitionRecipe",
    "TransitionScore",
    "TransitionScorer",
    "TransitionSelector",
    "SectionContext",
    "Stem",
    "StemAction",
    "SubgenrePairType",
    "TransitionIntent",
    "bpm_distance",
    "cosine_similarity",
    "correlation",
]
```

- [ ] **Step 6.3: Verify the whole package imports cleanly**

```bash
.venv/bin/python -c "
from app.transition import (
    TransitionScorer, TransitionSelector, TransitionRecipe,
    TransitionScore, SectionContext, bpm_distance
)
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 6.4: Run all currently-passing transition tests**

```bash
.venv/bin/python -m pytest tests/test_transition/test_types.py tests/test_transition/test_recipe.py tests/test_transition/test_selector.py tests/test_transition/test_subgenre_rules.py tests/test_domain/test_hard_constraints.py tests/test_domain/test_section_context.py tests/test_domain/test_transition_weights.py -v
```
Expected: all PASS

- [ ] **Step 6.5: Commit**

```text
refactor(transition): clean scorer.py + __init__.py — remove style.py dependency

scorer.py no longer re-exports recommend_style/style_profile.
__init__.py exports TransitionSelector, removes TransitionType.
```

---

## Task 7: Delete legacy files

**Files:**
- Delete: `app/transition/recipe_engine.py`
- Delete: `app/transition/style.py`
- Delete: `app/transition/neural_mix.py`
- Delete: `app/transition/legacy_recipe_map.py`
- Delete: `tests/test_transition/test_recipe_engine.py`
- Delete: `tests/test_transition/test_neural_mix.py`
- Delete: `tests/test_domain/test_transition_style.py`
- Delete: `tests/test_transition/test_recipe_integration.py` (rewrite in step below)

- [ ] **Step 7.1: Delete legacy source files**

```bash
rm app/transition/recipe_engine.py
rm app/transition/style.py
rm app/transition/neural_mix.py
rm app/transition/legacy_recipe_map.py
```

- [ ] **Step 7.2: Delete obsolete test files**

```bash
rm tests/test_transition/test_recipe_engine.py
rm tests/test_transition/test_neural_mix.py
rm tests/test_domain/test_transition_style.py
rm tests/test_transition/test_recipe_integration.py
```

- [ ] **Step 7.3: Write new integration test**

```python
# tests/test_transition/test_selector_integration.py
"""Integration test: full selector pipeline from score to recipe JSON."""
from app.core.constants import NeuralMixCrossfaderFX
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.selector import TransitionSelector

def _features(bpm: float = 128.0, lufs: float = -10.0) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, integrated_lufs=lufs)

def _score(**kwargs: float) -> TransitionScore:
    defaults = dict(bpm=0.85, harmonic=0.80, energy=0.80, spectral=0.80, groove=0.75, timbral=0.75, overall=0.80)
    defaults.update(kwargs)
    return TransitionScore(**defaults)

def test_full_pipeline_drum_swap():
    selector = TransitionSelector()
    score = _score(groove=0.80, overall=0.80)
    recipe = selector.build_recipe(score, _features(), _features())
    assert recipe.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP
    assert recipe.bars > 0

def test_full_pipeline_serialise_deserialise():
    selector = TransitionSelector()
    recipe = selector.build_recipe(_score(), _features(), _features())
    json_str = recipe.to_json()
    restored = TransitionRecipe.from_json(json_str)
    assert restored is not None
    assert restored.fx_type == recipe.fx_type
    assert restored.bars == recipe.bars
    assert len(restored.steps) == len(recipe.steps)

def test_hard_reject_gives_fade_recipe():
    selector = TransitionSelector()
    score = TransitionScore(hard_reject=True, reject_reason="bpm gap 15")
    recipe = selector.build_recipe(score, _features(), _features())
    assert recipe.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_FADE
    assert recipe.confidence < 0.7
```

- [ ] **Step 7.4: Run integration test**

```bash
.venv/bin/python -m pytest tests/test_transition/test_selector_integration.py -v
```
Expected: 3 PASS

- [ ] **Step 7.5: Verify no imports of deleted modules remain**

```bash
grep -rn "recipe_engine\|style\.recommend\|legacy_recipe_map\|neural_mix\|StyleRules\|DjayTransition\|TransitionType\|BASS_SWAP\|FILTER_SWEEP\|ECHO_OUT\|EQ_BLEND\|LONG_BLEND\|RISER\|DROP_SWAP\|DISSOLVE\|STEMS_CREATIVE\|CUT.*TransitionType" app/ --include="*.py" | grep -v "__pycache__"
```
Expected: no output (or only comments)

- [ ] **Step 7.6: Commit**

```sql
refactor(transition): delete 4 legacy files (recipe_engine, style, neural_mix, legacy_recipe_map)

Replaced by selector.py + existing recipe_decision.py + recipe_steps.py.
Deleted 1474 LOC, added ~150 LOC. 7 FX types remain, 12 legacy types gone.
```

---

## Task 8: Update consumers

**Files:**
- Modify: `app/services/set/scoring.py`
- Modify: `app/services/set/cheatsheet.py`

Both files call `recommend_recipe()` and `recommend_style()` from `app.transition`. Replace with `TransitionSelector`.

- [ ] **Step 8.1: Update `app/services/set/scoring.py`**

Find and replace all transition imports:

```python
# OLD (lines 15-24)
from app.transition import (
    SectionContext,
    TransitionRecipe,
    TransitionScore,
    recommend_recipe,
    recommend_style,
    style_profile,
)
from app.transition.math_helpers import bpm_distance
from app.transition.scorer import TransitionScorer

# NEW
from app.transition import (
    SectionContext,
    TransitionRecipe,
    TransitionScore,
    TransitionSelector,
)
from app.transition.math_helpers import bpm_distance
from app.transition.scorer import TransitionScorer
```

Then update usage sites (use `grep -n "recommend_style\|style_profile\|recommend_recipe" app/services/set/scoring.py` to find them):

```python
# OLD (around line 173)
style = recommend_style(synthetic)
profile_bars = style_profile(style)["bars"]

# NEW
_recipe = TransitionSelector().build_recipe(synthetic, feat_a, feat_b)
profile_bars = _recipe.bars
```

```python
# OLD (around line 185)
recipe = recommend_recipe(synthetic)

# NEW
recipe = TransitionSelector().build_recipe(synthetic, feat_from, feat_to)
```

```python
# OLD (around line 304)
recipe = recommend_recipe(
    ...
)
# NEW
recipe = TransitionSelector().build_recipe(
    score,
    feat_from,
    feat_to,
    section_context=section_context,
    mood_a=mood_a,
    mood_b=mood_b,
    intent=intent,
)
```

**Important:** Read the full context around each usage site before editing. The `recommend_recipe` signature was `recommend_recipe(score, features_a=None, features_b=None, ...)`. The new `TransitionSelector().build_recipe(score, features_a, features_b, ...)` requires explicit feature args; pass `TrackFeatures()` (all-None default) when features unavailable.

- [ ] **Step 8.2: Update `app/services/set/cheatsheet.py`**

```python
# OLD
from app.transition.style import recommend_recipe

# NEW
from app.transition.selector import TransitionSelector
```

Replace calls to `recommend_recipe(score, fa, fb)` with `TransitionSelector().build_recipe(score, fa, fb)`.

- [ ] **Step 8.3: Verify services import cleanly**

```bash
.venv/bin/python -c "from app.services.set.scoring import SetScoringService; print('OK')"
.venv/bin/python -c "from app.services.set.cheatsheet import generate_cheat_sheet; print('OK')" 2>/dev/null || .venv/bin/python -c "import app.services.set.cheatsheet; print('OK')"
```
Expected: both `OK`

- [ ] **Step 8.4: Run scoring service tests**

```bash
.venv/bin/python -m pytest tests/test_services/test_transition_scoring_p2.py -v
```
Expected: all PASS (if any import `recommend_recipe`, update them to `TransitionSelector`)

- [ ] **Step 8.5: Commit**

```text
fix(services): replace recommend_recipe/recommend_style with TransitionSelector

SetScoringService and cheatsheet no longer depend on deleted style.py.
TransitionSelector().build_recipe() is the single call site.
```

---

## Task 9: DB migration and model update

**Files:**
- Create: `app/db/migrations/versions/<hash>_add_fx_type_drop_transition_type.py`
- Modify: `app/db/models/transition.py` (if `transition_type` column exists there)

- [ ] **Step 9.1: Check if `transitions` table has `transition_type` column**

```bash
grep -n "transition_type\|fx_type" app/db/models/transition.py 2>/dev/null || echo "file not found"
```

If `transition_type` exists as a column, proceed with migration. If the model file doesn't define it (it may be in the DB but not in the model), still run the migration.

- [ ] **Step 9.2: Generate Alembic migration**

```bash
.venv/bin/python -m alembic revision --autogenerate -m "add_fx_type_drop_transition_type"
```

If autogenerate doesn't detect the change (because `transition_type` may not be in the SQLAlchemy model), write the migration manually:

```python
# In the generated migration file:
def upgrade() -> None:
    op.add_column(
        "transitions",
        sa.Column("fx_type", sa.String(length=30), nullable=True),
    )
    # Only drop if the column exists (it may already be absent from the model)
    with op.batch_alter_table("transitions") as batch_op:
        try:
            batch_op.drop_column("transition_type")
        except Exception:
            pass  # column already absent

def downgrade() -> None:
    op.add_column(
        "transitions",
        sa.Column("transition_type", sa.String(length=30), nullable=True),
    )
    with op.batch_alter_table("transitions") as batch_op:
        try:
            batch_op.drop_column("fx_type")
        except Exception:
            pass
```

- [ ] **Step 9.3: Update DB model if needed**

In `app/db/models/transition.py`, if `transition_type: Mapped[str | None]` exists:
- Replace with `fx_type: Mapped[str | None] = mapped_column(String(30), nullable=True)`

- [ ] **Step 9.4: Commit**

```text
feat(db): add fx_type column, drop legacy transition_type

fx_type stores NeuralMixCrossfaderFX values (7 options).
transition_type (14 legacy values) removed from schema.
```

---

## Task 10: Run full test suite and fix any remaining failures

- [ ] **Step 10.1: Run the full test suite**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```

- [ ] **Step 10.2: Fix any remaining import errors**

Common issues to look for:
- Any test still importing `from app.transition.style import ...` → update to `selector`
- Any test importing `recommend_style`, `style_profile`, `TransitionType`, `DjayTransition` → remove or replace
- Any test importing `from app.transition.weights import` → update to `constants`
- Any test importing `from app.transition.neural_mix import` → remove

For each failing test: read the error, make the minimal fix, re-run.

- [ ] **Step 10.3: Run `make check`**

```bash
make check
```

Expected: lint + typecheck + arch + tests all PASS.

If mypy fails on `selector.py` or `recipe.py`:
- Add missing type annotations
- Add `# type: ignore[...]` only for genuinely unresolvable FastMCP/library issues

- [ ] **Step 10.4: Final commit**

```bash
git add -p  # review each change
git commit -F /tmp/final.txt
```

Commit message:
```bash
test(transition): update all tests for Neural Mix refactor

Remove tests for deleted modules (recipe_engine, style, neural_mix).
Add test_selector.py and test_selector_integration.py.
All tests pass with new TransitionSelector-based architecture.
```

---

## Quick Reference: New Transition API

```python
# Score two tracks
scorer = TransitionScorer()
score = scorer.score(features_a, features_b, intent=intent, section_context=ctx)

# Select FX only
selector = TransitionSelector()
fx = selector.select(score, features_a, features_b, mood_a=mood_a, mood_b=mood_b)

# Build full recipe
recipe = selector.build_recipe(score, features_a, features_b,
                               section_context=ctx, mood_a=mood_a, mood_b=mood_b)

# Serialise to DB
json_str = recipe.to_json()

# Deserialise from DB
recipe = TransitionRecipe.from_json(json_str)  # returns None on invalid JSON
```

## Deleted / Replaced Symbol Reference

| Old symbol | New symbol |
|---|---|
| `recommend_recipe(score, fa, fb)` | `TransitionSelector().build_recipe(score, fa, fb)` |
| `recommend_style(score)` | `TransitionSelector().select(score, fa, fb)` |
| `style_profile(style)["bars"]` | `recipe.bars` (from `build_recipe`) |
| `TransitionRecipeEngine().generate(...)` | `TransitionSelector().build_recipe(...)` |
| `from app.transition.weights import X` | `from app.transition.constants import X` |
| `from app.transition.style import ...` | `from app.transition.selector import TransitionSelector` |
| `SubgenrePairType` (from subgenre_rules) | `from app.transition.types import SubgenrePairType` |
| `StemAction` (from recipe) | `from app.transition.types import StemAction` |
| `TransitionIntent` (from intent.py) | `from app.transition.types import TransitionIntent` |
