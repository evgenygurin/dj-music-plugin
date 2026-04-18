# Transition Recipe Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rule-based TransitionRecipeEngine that generates stem-level djay Pro AI instructions for 12 transition types, with subgenre-aware decision tree and enriched cheat sheets.

**Architecture:** New pure-domain layer `app/transition/recipe.py` + `recipe_engine.py` + `subgenre_rules.py` sitting between existing TransitionScorer and export/cheatsheet layers. No changes to scoring components, GA optimizer, or panel player.

**Tech Stack:** Python 3.12, dataclasses, StrEnum, Alembic (migration), pytest

**Spec:** `docs/superpowers/specs/2026-04-10-transition-recipe-engine-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `app/transition/recipe.py` | Data model: TransitionType, DjayTransition, StemAction, RecipeStep, EQPlan, TransitionRecipe |
| `app/transition/recipe_engine.py` | TransitionRecipeEngine: decision tree + step generation |
| `app/transition/subgenre_rules.py` | SubgenrePairType enum, classify_pair(), bar clamps, preferred types |
| `tests/test_transition/test_recipe.py` | Unit tests for data model serialization |
| `tests/test_transition/test_recipe_engine.py` | Decision tree tests (~25 cases) |
| `tests/test_transition/test_subgenre_rules.py` | Subgenre classification + modifier tests |
| `tests/test_transition/test_recipe_integration.py` | End-to-end: score → recipe → cheat sheet text |
| `app/db/migrations/versions/xxxx_add_recipe_columns.py` | Alembic migration: 3 columns on transitions |

### Modified files
| File | Change |
|------|--------|
| `app/core/constants.py` | Add TransitionType enum (12 values), DjayTransition enum |
| `app/transition/__init__.py` | Re-export `recommend_recipe`, `TransitionRecipe`, `TransitionType` |
| `app/transition/style.py` | Add `recommend_recipe()` wrapper function |
| `app/db/models/transition.py` | Add 3 nullable columns: `transition_type`, `transition_bars`, `transition_recipe_json` |
| `app/services/set/scoring.py` | Call `recommend_recipe()` in `_format_pair_response()` and persist recipe |
| `app/services/set/cheatsheet.py` | Render recipe steps in cheat sheet output |
| `app/export/models.py` | Add fields to `ExportTransition`: `transition_bars`, `djay_transition`, `recipe_steps`, `eq_plan`, `rescue_move` |
| `app/export/cheatsheet_writer.py` | Render recipe box in file export |

---

## Task 1: Recipe Data Model

**Files:**
- Create: `app/transition/recipe.py`
- Modify: `app/core/constants.py`
- Test: `tests/test_transition/test_recipe.py`

- [ ] **Step 1: Write failing test for TransitionType enum**

```python
# tests/test_transition/test_recipe.py
from app.transition.recipe import TransitionType, DjayTransition, StemAction

def test_transition_type_has_12_values():
    assert len(TransitionType) == 12
    assert TransitionType.CUT == "cut"
    assert TransitionType.NEURAL_MIX_BLEND == "neural_mix_blend"
    assert TransitionType.STEMS_CREATIVE == "stems_creative"

def test_djay_transition_has_6_values():
    assert len(DjayTransition) == 6
    assert DjayTransition.NEURAL_MIX == "neural_mix"

def test_stem_action_values():
    assert StemAction.SWAP == "swap"
    assert StemAction.FADE_IN == "fade_in"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_transition/test_recipe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.transition.recipe'`

- [ ] **Step 3: Create recipe.py with enums**

```python
# app/transition/recipe.py
"""Transition recipe data model for djay Pro AI instructions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

class TransitionType(StrEnum):
    """12 transition types mapped to djay Pro AI capabilities."""

    CUT = "cut"
    BASS_SWAP_SHORT = "bass_swap_short"
    BASS_SWAP_LONG = "bass_swap_long"
    EQ_BLEND = "eq_blend"
    FILTER_SWEEP = "filter_sweep"
    ECHO_OUT = "echo_out"
    LONG_BLEND = "long_blend"
    RISER = "riser"
    DROP_SWAP = "drop_swap"
    NEURAL_MIX_BLEND = "neural_mix_blend"
    DISSOLVE = "dissolve"
    STEMS_CREATIVE = "stems_creative"

class DjayTransition(StrEnum):
    """Mapping to djay Pro AI Crossfader FX / Automix transition."""

    NONE = "none"
    FILTER = "filter"
    ECHO = "echo"
    TREMOLO = "tremolo"
    RISER = "riser"
    NEURAL_MIX = "neural_mix"

class StemAction(StrEnum):
    """Actions that can be performed on a stem via Neural Mix."""

    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_transition/test_recipe.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write failing test for RecipeStep and TransitionRecipe**

```python
# tests/test_transition/test_recipe.py (append)
import json

from app.transition.recipe import (
    EQPlan,
    RecipeStep,
    TransitionRecipe,
)

def test_recipe_step_creation():
    step = RecipeStep(
        bar=8,
        deck="both",
        action="BASS SWAP on the one",
        stem="bass",
        stem_action=StemAction.SWAP,
    )
    assert step.bar == 8
    assert step.stem == "bass"
    assert step.eq_band is None

def test_transition_recipe_creation():
    recipe = TransitionRecipe(
        transition_type=TransitionType.BASS_SWAP_SHORT,
        bars=8,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(
            RecipeStep(bar=0, deck="B", action="Start B, bass killed"),
            RecipeStep(bar=8, deck="both", action="BASS SWAP"),
        ),
        eq_plan=EQPlan(low="swap@bar8", mid="gradual", high="keep"),
        mix_in_section="intro",
        mix_out_section="outro",
        phrase_align=True,
        warnings=("BPM +2",),
        confidence=0.88,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
    assert recipe.bars == 8
    assert len(recipe.steps) == 2
    assert recipe.steps[0].deck == "B"

def test_recipe_to_dict():
    recipe = TransitionRecipe(
        transition_type=TransitionType.CUT,
        bars=0,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(),
        eq_plan=EQPlan(low="keep", mid="keep", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.95,
        subgenre_modifier=None,
        rescue_move="hard cut",
    )
    d = recipe.to_dict()
    assert d["transition_type"] == "cut"
    assert d["bars"] == 0
    # Must be JSON-serializable
    json.dumps(d)
```

- [ ] **Step 6: Implement RecipeStep, EQPlan, TransitionRecipe dataclasses**

Add to `app/transition/recipe.py`:

```python
@dataclass(frozen=True)
class RecipeStep:
    """One instruction within a transition recipe."""

    bar: int
    deck: Literal["A", "B", "both"]
    action: str
    stem: str | None = None
    stem_action: StemAction | None = None
    eq_band: str | None = None
    eq_value: float | None = None
    effect: str | None = None
    effect_param: float | None = None

    def to_dict(self) -> dict:
        d: dict = {"bar": self.bar, "deck": self.deck, "action": self.action}
        if self.stem:
            d["stem"] = self.stem
        if self.stem_action:
            d["stem_action"] = self.stem_action.value
        if self.eq_band:
            d["eq_band"] = self.eq_band
            d["eq_value"] = self.eq_value
        if self.effect:
            d["effect"] = self.effect
            d["effect_param"] = self.effect_param
        return d

@dataclass(frozen=True)
class EQPlan:
    """High-level EQ strategy per band."""

    low: str
    mid: str
    high: str

    def to_dict(self) -> dict:
        return {"low": self.low, "mid": self.mid, "high": self.high}

@dataclass(frozen=True)
class TransitionRecipe:
    """Complete transition recipe with djay Pro AI instructions."""

    transition_type: TransitionType
    bars: int
    djay_transition: DjayTransition
    djay_tempo_adjust: str
    steps: tuple[RecipeStep, ...]
    eq_plan: EQPlan
    mix_in_section: str | None
    mix_out_section: str | None
    phrase_align: bool
    warnings: tuple[str, ...]
    confidence: float
    subgenre_modifier: str | None
    rescue_move: str

    def to_dict(self) -> dict:
        return {
            "transition_type": self.transition_type.value,
            "bars": self.bars,
            "djay_transition": self.djay_transition.value,
            "djay_tempo_adjust": self.djay_tempo_adjust,
            "steps": [s.to_dict() for s in self.steps],
            "eq_plan": self.eq_plan.to_dict(),
            "mix_in_section": self.mix_in_section,
            "mix_out_section": self.mix_out_section,
            "phrase_align": self.phrase_align,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "subgenre_modifier": self.subgenre_modifier,
            "rescue_move": self.rescue_move,
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict())
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/test_transition/test_recipe.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Commit**

```bash
feat(transition): add TransitionRecipe data model

Frozen dataclasses for 12 transition types, stem actions, recipe
steps, and EQ plans. JSON serializable for DB persistence.
```

---

## Task 2: Subgenre Rules

**Files:**
- Create: `app/transition/subgenre_rules.py`
- Test: `tests/test_transition/test_subgenre_rules.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transition/test_subgenre_rules.py
from app.core.constants import TechnoSubgenre
from app.transition.subgenre_rules import (
    SubgenrePairType,
    classify_pair,
    clamp_bars,
    preferred_type_for_pair,
)
from app.transition.recipe import TransitionType

def test_classify_ambient_pair():
    result = classify_pair(TechnoSubgenre.DUB_TECHNO, TechnoSubgenre.AMBIENT_DUB)
    assert result == SubgenrePairType.AMBIENT_PAIR

def test_classify_hard_pair():
    result = classify_pair(TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO)
    assert result == SubgenrePairType.HARD_PAIR

def test_classify_acid_pair():
    result = classify_pair(TechnoSubgenre.ACID, TechnoSubgenre.DRIVING)
    assert result == SubgenrePairType.ACID_PAIR

def test_classify_melodic_pair():
    result = classify_pair(TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE)
    assert result == SubgenrePairType.MELODIC_PAIR

def test_classify_hypnotic_pair():
    result = classify_pair(TechnoSubgenre.MINIMAL, TechnoSubgenre.HYPNOTIC)
    assert result == SubgenrePairType.HYPNOTIC_PAIR

def test_classify_mixed_pair():
    result = classify_pair(TechnoSubgenre.PEAK_TIME, TechnoSubgenre.DUB_TECHNO)
    assert result == SubgenrePairType.MIXED_PAIR

def test_classify_none_mood():
    result = classify_pair(None, TechnoSubgenre.DRIVING)
    assert result == SubgenrePairType.MIXED_PAIR

def test_clamp_bars_ambient():
    assert clamp_bars(16, SubgenrePairType.AMBIENT_PAIR) == 32

def test_clamp_bars_hard():
    assert clamp_bars(32, SubgenrePairType.HARD_PAIR) == 8

def test_clamp_bars_hypnotic():
    assert clamp_bars(8, SubgenrePairType.HYPNOTIC_PAIR) == 16

def test_clamp_bars_mixed_no_change():
    assert clamp_bars(16, SubgenrePairType.MIXED_PAIR) == 16

def test_preferred_type_ambient():
    tt = preferred_type_for_pair(SubgenrePairType.AMBIENT_PAIR)
    assert TransitionType.DISSOLVE in tt
    assert TransitionType.LONG_BLEND in tt

def test_preferred_type_hard():
    tt = preferred_type_for_pair(SubgenrePairType.HARD_PAIR)
    assert TransitionType.CUT in tt
    assert TransitionType.DROP_SWAP in tt
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transition/test_subgenre_rules.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement subgenre_rules.py**

```python
# app/transition/subgenre_rules.py
"""Subgenre-specific transition rules for techno pair classification."""

from __future__ import annotations

from enum import StrEnum

from app.core.constants import TechnoSubgenre
from app.transition.recipe import TransitionType

_AMBIENT = frozenset({TechnoSubgenre.AMBIENT_DUB, TechnoSubgenre.DUB_TECHNO})
_HARD = frozenset({TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO, TechnoSubgenre.RAW})
_MELODIC = frozenset({TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE, TechnoSubgenre.DETROIT})
_HYPNOTIC = frozenset({TechnoSubgenre.HYPNOTIC, TechnoSubgenre.MINIMAL})

class SubgenrePairType(StrEnum):
    AMBIENT_PAIR = "ambient_pair"
    HARD_PAIR = "hard_pair"
    ACID_PAIR = "acid_pair"
    MELODIC_PAIR = "melodic_pair"
    HYPNOTIC_PAIR = "hypnotic_pair"
    MIXED_PAIR = "mixed_pair"

def classify_pair(
    mood_a: TechnoSubgenre | str | None,
    mood_b: TechnoSubgenre | str | None,
) -> SubgenrePairType:
    """Classify a pair of tracks by their combined subgenre context."""
    if mood_a is None or mood_b is None:
        return SubgenrePairType.MIXED_PAIR

    a = TechnoSubgenre(mood_a) if isinstance(mood_a, str) else mood_a
    b = TechnoSubgenre(mood_b) if isinstance(mood_b, str) else mood_b

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

_BAR_CLAMPS: dict[SubgenrePairType, tuple[int, int]] = {
    SubgenrePairType.AMBIENT_PAIR: (32, 128),
    SubgenrePairType.HARD_PAIR: (0, 8),
    SubgenrePairType.HYPNOTIC_PAIR: (16, 64),
    SubgenrePairType.ACID_PAIR: (8, 32),
    SubgenrePairType.MELODIC_PAIR: (16, 64),
    SubgenrePairType.MIXED_PAIR: (0, 64),
}

def clamp_bars(bars: int, pair_type: SubgenrePairType) -> int:
    lo, hi = _BAR_CLAMPS.get(pair_type, (0, 64))
    return max(lo, min(bars, hi))

_PREFERRED_TYPES: dict[SubgenrePairType, tuple[TransitionType, ...]] = {
    SubgenrePairType.AMBIENT_PAIR: (TransitionType.DISSOLVE, TransitionType.LONG_BLEND),
    SubgenrePairType.HARD_PAIR: (TransitionType.CUT, TransitionType.DROP_SWAP, TransitionType.FILTER_SWEEP),
    SubgenrePairType.ACID_PAIR: (TransitionType.FILTER_SWEEP,),
    SubgenrePairType.MELODIC_PAIR: (TransitionType.EQ_BLEND, TransitionType.LONG_BLEND),
    SubgenrePairType.HYPNOTIC_PAIR: (TransitionType.NEURAL_MIX_BLEND, TransitionType.EQ_BLEND),
    SubgenrePairType.MIXED_PAIR: (TransitionType.EQ_BLEND, TransitionType.FILTER_SWEEP),
}

def preferred_type_for_pair(pair_type: SubgenrePairType) -> tuple[TransitionType, ...]:
    return _PREFERRED_TYPES.get(pair_type, (TransitionType.EQ_BLEND,))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_transition/test_subgenre_rules.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```text
feat(transition): add subgenre pair classification rules

Classifies track pairs into 6 categories (ambient, hard, acid,
melodic, hypnotic, mixed) with bar clamps and preferred types.
```

---

## Task 3: Recipe Engine — Decision Tree

**Files:**
- Create: `app/transition/recipe_engine.py`
- Test: `tests/test_transition/test_recipe_engine.py`

- [ ] **Step 1: Write failing tests for decision tree — first 8 key paths**

```python
# tests/test_transition/test_recipe_engine.py
from app.core.constants import TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import DjayTransition, TransitionRecipe, TransitionType
from app.transition.recipe_engine import TransitionRecipeEngine
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.core.constants import SectionType

engine = TransitionRecipeEngine()

# --- Helpers ---

def _features(**kw) -> TrackFeatures:
    defaults = dict(bpm=130.0, key_code=15, integrated_lufs=-8.0,
                    spectral_centroid_hz=2000.0, energy_mean=0.5,
                    kick_prominence=0.5, onset_rate=4.0, hp_ratio=1.5,
                    bpm_stability=0.9, bpm_confidence=0.8,
                    pitch_salience_mean=0.2, mfcc_vector=[0.0]*13)
    defaults.update(kw)
    return TrackFeatures(**defaults)

FA = _features()
FB = _features()

# --- Step 1: Hard reject ---

def test_hard_reject_gives_filter_sweep():
    score = TransitionScore(hard_reject=True, reject_reason="BPM diff 14")
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP
    assert recipe.bars == 16
    assert recipe.djay_transition == DjayTransition.FILTER
    assert recipe.confidence < 0.65

# --- Step 2: Drum-only pair ---

def test_drum_only_high_groove_gives_cut():
    score = TransitionScore(bpm=0.9, harmonic=0.8, energy=0.8,
                            spectral=0.7, groove=0.85, timbral=0.7, overall=0.8)
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    recipe = engine.generate(score, FA, FB, section_context=ctx)
    assert recipe.transition_type == TransitionType.CUT
    assert recipe.bars == 0

# --- Step 3: Spectral collision ---

def test_spectral_collision_gives_filter_sweep():
    score = TransitionScore(spectral=0.30, bpm=0.8, harmonic=0.7,
                            energy=0.7, groove=0.6, timbral=0.6, overall=0.6)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP

# --- Step 4: Key clash + compatible drums ---

def test_key_clash_compatible_drums_gives_neural_mix():
    score = TransitionScore(harmonic=0.40, groove=0.80, bpm=0.9,
                            energy=0.7, spectral=0.6, timbral=0.6, overall=0.65)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.NEURAL_MIX_BLEND
    assert recipe.djay_transition == DjayTransition.NEURAL_MIX

# --- Step 5: Energy gap + ramp up ---

def test_energy_gap_ramp_up_hard_gives_riser():
    score = TransitionScore(energy=0.30, bpm=0.9, harmonic=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.6)
    fa = _features(integrated_lufs=-10.0)
    fb = _features(integrated_lufs=-6.0)
    recipe = engine.generate(score, fa, fb,
                             mood_a=TechnoSubgenre.HARD_TECHNO,
                             mood_b=TechnoSubgenre.INDUSTRIAL)
    assert recipe.transition_type == TransitionType.RISER

# --- Step 6: Subgenre-specific ---

def test_ambient_pair_gives_dissolve():
    score = TransitionScore(bpm=0.9, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.7)
    recipe = engine.generate(score, FA, FB,
                             mood_a=TechnoSubgenre.DUB_TECHNO,
                             mood_b=TechnoSubgenre.AMBIENT_DUB)
    assert recipe.transition_type == TransitionType.DISSOLVE
    assert recipe.bars >= 32

def test_hard_pair_high_score_gives_drop_swap():
    score = TransitionScore(bpm=0.9, harmonic=0.8, energy=0.8,
                            spectral=0.7, groove=0.7, timbral=0.7, overall=0.75)
    recipe = engine.generate(score, FA, FB,
                             mood_a=TechnoSubgenre.INDUSTRIAL,
                             mood_b=TechnoSubgenre.HARD_TECHNO)
    assert recipe.transition_type == TransitionType.DROP_SWAP
    assert recipe.bars <= 8

# --- Step 7: Vocal conflict ---

def test_vocal_conflict_gives_drop_swap_or_neural():
    score = TransitionScore(bpm=0.9, harmonic=0.8, energy=0.8,
                            spectral=0.7, groove=0.7, timbral=0.7, overall=0.80)
    fa = _features(pitch_salience_mean=0.55, spectral_centroid_hz=3200)
    fb = _features(pitch_salience_mean=0.50, spectral_centroid_hz=2800)
    recipe = engine.generate(score, fa, fb)
    assert recipe.transition_type in {TransitionType.DROP_SWAP, TransitionType.NEURAL_MIX_BLEND}
    assert any("vocal" in w.lower() for w in recipe.warnings)

# --- Step 8: Perfect match ---

def test_perfect_match_gives_cut_or_bass_swap():
    score = TransitionScore(bpm=0.98, harmonic=0.90, energy=0.85,
                            spectral=0.85, groove=0.80, timbral=0.80, overall=0.90)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type in {TransitionType.CUT, TransitionType.BASS_SWAP_SHORT}

# --- Graduated fallback ---

def test_overall_080_gives_bass_swap_short():
    score = TransitionScore(bpm=0.8, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.82)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.BASS_SWAP_SHORT

def test_overall_065_gives_eq_blend():
    score = TransitionScore(bpm=0.7, harmonic=0.6, energy=0.6,
                            spectral=0.6, groove=0.5, timbral=0.5, overall=0.68)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.EQ_BLEND

def test_overall_050_gives_bass_swap_long():
    score = TransitionScore(bpm=0.6, harmonic=0.5, energy=0.5,
                            spectral=0.5, groove=0.5, timbral=0.5, overall=0.55)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.BASS_SWAP_LONG

def test_low_overall_gives_filter_sweep():
    score = TransitionScore(bpm=0.4, harmonic=0.4, energy=0.5,
                            spectral=0.5, groove=0.4, timbral=0.4, overall=0.42)
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP

# --- Post-processing ---

def test_phrase_snap_to_8():
    """Bars snap to nearest 8-bar phrase boundary."""
    score = TransitionScore(bpm=0.8, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.82)
    recipe = engine.generate(score, FA, FB)
    assert recipe.bars % 8 == 0

def test_recipe_has_steps():
    score = TransitionScore(bpm=0.8, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.82)
    recipe = engine.generate(score, FA, FB)
    assert len(recipe.steps) > 0
    assert all(isinstance(s.bar, int) for s in recipe.steps)
    assert all(s.deck in ("A", "B", "both") for s in recipe.steps)

def test_recipe_has_rescue_move():
    score = TransitionScore(bpm=0.8, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.82)
    recipe = engine.generate(score, FA, FB)
    assert recipe.rescue_move
    assert len(recipe.rescue_move) > 5

def test_recipe_confidence_in_range():
    score = TransitionScore(bpm=0.8, harmonic=0.7, energy=0.7,
                            spectral=0.6, groove=0.6, timbral=0.6, overall=0.82)
    recipe = engine.generate(score, FA, FB)
    assert 0.0 <= recipe.confidence <= 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transition/test_recipe_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.transition.recipe_engine'`

- [ ] **Step 3: Implement TransitionRecipeEngine with decision tree + step templates**

Create `app/transition/recipe_engine.py`. This is a large file (~350 lines) containing:

1. `TransitionRecipeEngine` class with `generate()` method implementing the full decision tree from the spec (Steps 1-12 + post-processing)
2. `_select_type()` — the decision tree returning `(TransitionType, bars, DjayTransition, confidence)`
3. `_build_steps()` — dispatches to per-type step template functions
4. `_steps_cut()`, `_steps_bass_swap_short()`, `_steps_bass_swap_long()`, `_steps_eq_blend()`, `_steps_filter_sweep()`, `_steps_echo_out()`, `_steps_long_blend()`, `_steps_riser()`, `_steps_drop_swap()`, `_steps_neural_mix_blend()`, `_steps_dissolve()`, `_steps_stems_creative()` — 12 step template functions
5. `_detect_vocal_likely()` — heuristic: `pitch_salience_mean > 0.4 and spectral_centroid_hz > 2500`
6. `_snap_to_phrase()` — round bars to nearest 8
7. `_build_warnings()` — generate BPM delta, key distance warnings
8. `_select_rescue_move()` — per-type rescue recommendations

Key implementation details:
- `generate()` signature matches spec exactly (see Task 3 Step 1 test fixtures)
- Decision tree priority order matches spec Section 5 exactly
- Step templates follow canonical stem swap order: drums → bass → harmonics → vocals
- `_snap_to_phrase(bars)` → `max(0, round(bars / 8) * 8)` (but 0 stays 0 for CUT/DROP_SWAP)
- Uses `classify_pair()` and `clamp_bars()` from `subgenre_rules.py`

The engineer should implement this file following the decision tree from `docs/superpowers/specs/2026-04-10-transition-recipe-engine-design.md` Section 5, using the exact field names from `TransitionScore` (`bpm`, `harmonic`, `energy`, `spectral`, `groove`, `timbral`, `overall`, `hard_reject`) and `TrackFeatures` (`integrated_lufs`, `pitch_salience_mean`, `spectral_centroid_hz`).

- [ ] **Step 4: Run tests iteratively until all pass**

Run: `uv run pytest tests/test_transition/test_recipe_engine.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Run full transition test suite**

Run: `uv run pytest tests/test_transition/ -v`
Expected: All PASS (existing + new)

- [ ] **Step 6: Commit**

```text
feat(transition): add TransitionRecipeEngine with 12-type decision tree

Rule-based engine selecting from 12 djay Pro AI transition types
based on scores, features, subgenres, and section context.
Generates step-by-step stem/EQ/effect instructions.
```

---

## Task 4: Wire into __init__.py and style.py

**Files:**
- Modify: `app/transition/__init__.py`
- Modify: `app/transition/style.py`

- [ ] **Step 1: Write failing test for recommend_recipe**

```python
# tests/test_transition/test_recipe_integration.py
from app.transition import recommend_recipe, TransitionRecipe, TransitionType
from app.transition.score import TransitionScore
from app.entities.audio.features import TrackFeatures

def test_recommend_recipe_with_features():
    score = TransitionScore(bpm=0.9, harmonic=0.8, energy=0.8,
                            spectral=0.7, groove=0.7, timbral=0.7, overall=0.82)
    fa = TrackFeatures(bpm=130.0, key_code=15, integrated_lufs=-8.0)
    fb = TrackFeatures(bpm=132.0, key_code=16, integrated_lufs=-7.5)
    recipe = recommend_recipe(score, fa, fb)
    assert isinstance(recipe, TransitionRecipe)
    assert recipe.bars >= 0

def test_recommend_recipe_fallback_without_features():
    score = TransitionScore(bpm=0.9, harmonic=0.8, energy=0.8,
                            spectral=0.7, groove=0.7, timbral=0.7, overall=0.82)
    recipe = recommend_recipe(score)
    assert isinstance(recipe, TransitionRecipe)
    # Fallback from recommend_style → basic recipe
    assert recipe.transition_type in TransitionType
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py -v`
Expected: FAIL — `cannot import name 'recommend_recipe'`

- [ ] **Step 3: Add recommend_recipe to style.py**

```python
# app/transition/style.py (add at end of file)

from app.transition.recipe import TransitionRecipe, TransitionType, DjayTransition, EQPlan
from app.transition.recipe_engine import TransitionRecipeEngine
from app.entities.audio.features import TrackFeatures

def recommend_recipe(
    score: TransitionScore,
    features_a: TrackFeatures | None = None,
    features_b: TrackFeatures | None = None,
    **kwargs,
) -> TransitionRecipe:
    """Generate full transition recipe. Falls back to style-based if no features."""
    if features_a is not None and features_b is not None:
        engine = TransitionRecipeEngine()
        return engine.generate(score, features_a, features_b, **kwargs)
    # Fallback: convert old style to basic recipe
    style = recommend_style(score)
    profile = style_profile(style)
    return TransitionRecipe(
        transition_type=TransitionType(style.value),
        bars=int(profile["bars"]),
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(),
        eq_plan=EQPlan(low="keep", mid="keep", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.5,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
```

- [ ] **Step 4: Update __init__.py**

Add to `app/transition/__init__.py` imports and `__all__`:
- `recommend_recipe` from `app.transition.style`
- `TransitionRecipe`, `TransitionType` from `app.transition.recipe`

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/test_transition/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```text
feat(transition): wire recommend_recipe into public API

Backward-compatible wrapper: uses engine when features available,
falls back to style-based recipe otherwise.
```

---

## Task 5: DB Migration

**Files:**
- Create: `app/db/migrations/versions/xxxx_add_recipe_columns.py`
- Modify: `app/db/models/transition.py`

- [ ] **Step 1: Add columns to Transition model**

Add to `app/db/models/transition.py` in `Transition` class, after `overall_quality`:

```python
    transition_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transition_bars: Mapped[int | None] = mapped_column(nullable=True)
    transition_recipe_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Import `String, Text` from `sqlalchemy` if not already imported.

- [ ] **Step 2: Generate Alembic migration**

Run: `uv run alembic revision --autogenerate -m "add transition recipe columns"`
Expected: New migration file created

- [ ] **Step 3: Review migration, verify 3 ADD COLUMN operations**

Read the generated migration file and verify it contains:
```python
op.add_column('transitions', sa.Column('transition_type', sa.String(30), nullable=True))
op.add_column('transitions', sa.Column('transition_bars', sa.Integer(), nullable=True))
op.add_column('transitions', sa.Column('transition_recipe_json', sa.Text(), nullable=True))
```

- [ ] **Step 4: Run existing tests to verify no breakage**

Run: `uv run pytest tests/test_repositories/ -v -x`
Expected: All PASS (in-memory SQLite creates columns automatically)

- [ ] **Step 5: Commit**

```text
feat(db): add transition recipe columns

Three nullable columns on transitions table: transition_type,
transition_bars, transition_recipe_json. Non-breaking migration.
```

---

## Task 6: Wire into SetScoringService

**Files:**
- Modify: `app/services/set/scoring.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_transition/test_recipe_integration.py (append)

def test_format_pair_response_includes_recipe():
    """_format_pair_response should include recipe data when available."""
    from app.services.set.scoring import SetScoringService

    response = SetScoringService._format_pair_response(
        from_track_id=1, to_track_id=2,
        bpm=0.9, harmonic=0.8, energy=0.8,
        spectral=0.7, groove=0.7, timbral=0.7,
        overall=0.82, hard_reject=False, reject_reason=None,
        cached=False,
    )
    assert "recommended_style" in response
    # New: recipe data
    assert "transition_type" in response
    assert "transition_bars" in response
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py::test_format_pair_response_includes_recipe -v`
Expected: FAIL — `transition_type` not in response

- [ ] **Step 3: Modify _format_pair_response in scoring.py**

In `app/services/set/scoring.py`, in `_format_pair_response()`, after the existing `recommended_style` / `recommended_bars` lines, add:

```python
        # Recipe (enhanced transition instructions)
        recipe = recommend_recipe(synthetic, features_a, features_b)
        result["transition_type"] = recipe.transition_type.value
        result["transition_bars"] = recipe.bars
        result["djay_transition"] = recipe.djay_transition.value
        result["recipe_confidence"] = recipe.confidence
```

Note: `_format_pair_response` is a `@staticmethod` and currently doesn't receive `TrackFeatures`. It needs to accept optional `features_a` and `features_b` parameters. If the method signature doesn't allow it cleanly, call `recommend_recipe(synthetic)` without features (fallback mode) and wire features in the callers (`score_pair`, `score_set_transitions`) where features are already loaded.

Add import at top: `from app.transition.style import recommend_recipe`

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
feat(scoring): include transition recipe in pair response

score_pair and score_set_transitions now return transition_type,
transition_bars, djay_transition alongside existing recommended_style.
```

---

## Task 7: Enrich Cheat Sheet

**Files:**
- Modify: `app/services/set/cheatsheet.py`
- Modify: `app/export/cheatsheet_writer.py`
- Modify: `app/export/models.py`

- [ ] **Step 1: Write failing test for enriched cheat sheet**

```python
# tests/test_transition/test_recipe_integration.py (append)

def test_cheat_sheet_contains_recipe_box():
    """Cheat sheet text should include transition type and steps."""
    # This is a format test — we check the output string
    from app.services.set.cheatsheet import _format_recipe_box
    from app.transition.recipe import (
        TransitionRecipe, TransitionType, DjayTransition,
        EQPlan, RecipeStep,
    )

    recipe = TransitionRecipe(
        transition_type=TransitionType.BASS_SWAP_SHORT,
        bars=16,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(
            RecipeStep(bar=0, deck="B", action="Start B, bass killed"),
            RecipeStep(bar=8, deck="both", action="BASS SWAP on the one"),
        ),
        eq_plan=EQPlan(low="swap@bar8", mid="gradual", high="keep"),
        mix_in_section="intro",
        mix_out_section="outro",
        phrase_align=True,
        warnings=("BPM +2",),
        confidence=0.88,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
    text = _format_recipe_box(recipe, score=0.85)
    assert "BASS SWAP SHORT" in text
    assert "16 bars" in text
    assert "bar 0" in text
    assert "bar 8" in text
    assert "BASS SWAP on the one" in text
    assert "swap@bar8" in text
    assert "Rescue" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py::test_cheat_sheet_contains_recipe_box -v`
Expected: FAIL — `cannot import name '_format_recipe_box'`

- [ ] **Step 3: Add _format_recipe_box to cheatsheet.py**

Add to `app/services/set/cheatsheet.py`:

```python
def _format_recipe_box(recipe: TransitionRecipe, score: float | None = None) -> str:
    """Format a transition recipe as a text box for cheat sheet."""
    from app.transition.recipe import TransitionRecipe

    header = (
        f"  {recipe.transition_type.value.upper().replace('_', ' ')} "
        f"· {recipe.bars} bars"
    )
    if recipe.djay_transition.value != "none":
        header += f" ─── djay: {recipe.djay_transition.value.replace('_', ' ').title()}"
    else:
        header += " ─── djay: Manual EQ"

    lines = [f"     ┌── {header} ──┐"]
    lines.append("     │")
    for step in recipe.steps:
        deck_label = step.deck.upper()
        lines.append(f"     │  bar {step.bar:<3}  {deck_label}: {step.action}")
    lines.append("     │")
    eq = recipe.eq_plan
    lines.append(f"     │  EQ: low={eq.low} · mid={eq.mid} · high={eq.high}")
    for w in recipe.warnings:
        lines.append(f"     │  ⚠ {w}")
    lines.append(f"     │  🛟 Rescue: {recipe.rescue_move}")
    if score is not None:
        lines.append(f"     │  Score: {score:.2f} · Confidence: {recipe.confidence:.2f}")
    lines.append("     └" + "─" * 50 + "┘")
    return "\n".join(lines)
```

- [ ] **Step 4: Integrate into get_cheat_sheet method**

In `SetCheatSheetService.get_cheat_sheet()`, after the current `->` transition line, add a recipe box if recipe data is available. This requires loading features and generating recipes for each pair. The simplest approach: call `recommend_recipe(synthetic_score, features_a, features_b)` inline and append `_format_recipe_box()` output.

- [ ] **Step 5: Add fields to ExportTransition**

In `app/export/models.py`, add to `ExportTransition`:

```python
    transition_bars: int | None = None
    djay_transition: str | None = None
    recipe_steps: list[dict] | None = None
    eq_plan: dict | None = None
    rescue_move: str | None = None
```

- [ ] **Step 6: Update cheatsheet_writer.py**

In `app/export/cheatsheet_writer.py`, `write_cheat_sheet()`, after the existing transition line, add recipe box rendering using the same `_format_recipe_box` logic (import from cheatsheet.py or duplicate as standalone).

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_transition/test_recipe_integration.py -v`
Expected: PASS

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All PASS

- [ ] **Step 9: Commit**

```text
feat(cheatsheet): render recipe boxes with step-by-step instructions

Both MCP cheat sheet and file export now include transition type,
bar-by-bar stem/EQ/effect instructions, and rescue moves.
```

---

## Task 8: Lint, Type-check, Full Validation

**Files:** none (validation only)

- [ ] **Step 1: Ruff check**

Run: `uv run ruff check app/transition/recipe.py app/transition/recipe_engine.py app/transition/subgenre_rules.py`
Expected: No errors

- [ ] **Step 2: Ruff format check**

Run: `uv run ruff format --check app/transition/`
Expected: All formatted

- [ ] **Step 3: Mypy**

Run: `uv run mypy app/transition/recipe.py app/transition/recipe_engine.py app/transition/subgenre_rules.py`
Expected: No errors

- [ ] **Step 4: Import linter**

Run: `uv run lint-imports`
Expected: All contracts pass (recipe.py is in transition/ which is Band 3 pure — no DB/HTTP imports)

- [ ] **Step 5: Full test suite**

Run: `uv run pytest -v`
Expected: All ~1200+ tests PASS

- [ ] **Step 6: Commit (if any lint fixes)**

```bash
style: fix lint issues in transition recipe engine
```

---

## Summary

| Task | Description | New tests | Files |
|------|-------------|-----------|-------|
| 1 | Recipe data model | 6 | recipe.py |
| 2 | Subgenre rules | 13 | subgenre_rules.py |
| 3 | Recipe engine (decision tree + steps) | 16 | recipe_engine.py |
| 4 | Wire into public API | 2 | style.py, __init__.py |
| 5 | DB migration | 0 (uses existing) | migration, transition.py |
| 6 | Wire into scoring service | 1 | scoring.py |
| 7 | Enrich cheat sheet + export | 1 | cheatsheet.py, models.py, writer.py |
| 8 | Lint + validation | 0 | — |
| **Total** | | **~39 tests** | **3 new + 7 modified** |
