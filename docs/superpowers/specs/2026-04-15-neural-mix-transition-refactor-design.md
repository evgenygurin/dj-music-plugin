# Neural Mix Transition Refactor — Design Spec

**Date:** 2026-04-15  
**Status:** Approved  
**Scope:** `app/transition/` full refactor + consumers update + DB migration

---

## 1. Context and Problem

### Current state

The `app/transition/` module has 16 files (~2770 LOC) with multiple architectural problems:

- **Broken import chain.** `TransitionType` is referenced in `__init__.py`, `style.py`, `recipe_decision.py`, `subgenre_rules.py`, `recipe_engine.py` — but is never defined anywhere.
- **Legacy dual-pathway.** `legacy_recipe_map.py` maps 14 old `transition_type` values (CUT, BASS_SWAP_SHORT, LONG_BLEND, FILTER_SWEEP, RISER, DROP_SWAP, DISSOLVE, STEMS_CREATIVE, EQ_BLEND, NEURAL_MIX_BLEND…) to `NeuralMixCrossfaderFX`. These types no longer exist in djay Pro AI.
- **Duplicate responsibility.** `style.py` + `recipe_decision.py` + `recipe_engine.py` + `recipe_steps.py` all solve one problem: "pick a transition FX and build a recipe." Four files, overlapping logic, no single authority.
- **Scattered constants.** Magic numbers appear in `weights.py`, `recipe_decision.py`, `recipe_steps.py`, `neural_mix.py`, `subgenre_rules.py`.
- **DB inconsistency.** `transitions` table has both `transition_type VARCHAR(30)` (14 legacy values, nullable) and `transition_recipe_json TEXT` (new recipe, nullable). Column `transition_type` is dead weight.

### Canonical FX set (djay Pro AI)

djay Pro AI exposes exactly 7 Neural Mix Crossfader FX. These are the only valid transition types going forward:

| FX | Behaviour |
|---|---|
| `neural_mix_fade` | Classic crossfade of all stems |
| `neural_mix_echo_out` | Echo tail on outgoing track, cut drums first |
| `neural_mix_vocal_sustain` | Vocals of A sustain over instrumental of B |
| `neural_mix_harmonic_sustain` | Harmonics of A sustain over drums of B |
| `neural_mix_drum_swap` | Swap only the drum stem at the transition point |
| `neural_mix_vocal_cut` | Cut vocals at crossover (sharp, energy preserved) |
| `neural_mix_drum_cut` | Cut drums at crossover (drop moment) |

`NeuralMixCrossfaderFX` StrEnum with these 7 values already exists in `app/core/constants.py`. It remains the canonical source of truth and is not moved.

---

## 2. Target Architecture

### 2.1 Directory layout

```text
app/transition/
├── __init__.py              # Public API re-exports only
├── types.py                 # Stem, StemAction, TransitionIntent enums
├── constants.py             # ALL magic numbers: weights, thresholds, bar counts per FX
├── score.py                 # TransitionScore dataclass (unchanged)
├── section_context.py       # SectionContext (unchanged)
├── hard_constraints.py      # check_hard_constraints() (unchanged)
├── math_helpers.py          # bpm_distance, cosine_similarity, correlation (unchanged)
├── intent.py                # infer_intent(template, position, energy_delta)
├── components/              # 6 component scorers — unchanged
│   ├── __init__.py
│   ├── bpm.py
│   ├── harmonic.py
│   ├── energy.py
│   ├── spectral.py
│   ├── groove.py
│   └── timbral.py
├── scorer.py                # TransitionScorer (Facade over 6 components)
├── recipe.py                # TransitionRecipe, RecipeStep dataclasses
├── fx/                      # Strategy pattern — one file per FX
│   ├── __init__.py          # FX_REGISTRY dict + get_strategy()
│   ├── base.py              # FXStrategy ABC: applicability() + build_recipe()
│   ├── fade.py
│   ├── echo_out.py
│   ├── vocal_sustain.py
│   ├── harmonic_sustain.py
│   ├── drum_swap.py
│   ├── vocal_cut.py
│   └── drum_cut.py
└── selector.py              # TransitionSelector — picks argmax(strategy.applicability)
```

### 2.2 Files deleted

| File | Reason |
|---|---|
| `legacy_recipe_map.py` | Legacy 14-type mapping no longer needed |
| `recipe_engine.py` | Replaced by `fx/*.py` + `selector.py` |
| `recipe_decision.py` | Replaced by `selector.py` + `fx/base.py` |
| `recipe_steps.py` | Replaced by `fx/*.py` build_recipe() methods |
| `style.py` | Replaced by `selector.py` |
| `subgenre_rules.py` | Rules migrated into relevant `fx/*.py` strategies |
| `neural_mix.py` | Stem-scoring merged into `fx/base.py` and individual strategies |
| `weights.py` | Renamed and restructured as `constants.py` |

---

## 3. Key Abstractions

### 3.1 `FXStrategy` (Strategy pattern)

```python
# app/transition/fx/base.py
class FXStrategy(ABC):
    fx_type: ClassVar[NeuralMixCrossfaderFX]  # identity

    @abstractmethod
    def applicability(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        context: SectionContext | None = None,
    ) -> float:
        """Return 0..1 — how well this FX fits the transition."""

    @abstractmethod
    def build_recipe(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        context: SectionContext | None = None,
    ) -> TransitionRecipe:
        """Return bar-by-bar step sequence for this FX."""
```

Each of 7 FX files contains exactly one subclass.

### 3.2 FX Registry (Registry pattern)

```python
# app/transition/fx/__init__.py
FX_REGISTRY: dict[NeuralMixCrossfaderFX, FXStrategy] = {
    NeuralMixCrossfaderFX.NEURAL_MIX_FADE: FadeStrategy(),
    NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT: EchoOutStrategy(),
    # …
}

def get_strategy(fx: NeuralMixCrossfaderFX) -> FXStrategy:
    return FX_REGISTRY[fx]
```

Adding a new FX = new file + one entry in `FX_REGISTRY`. Core code unchanged (Open/Closed).

### 3.3 `TransitionSelector` (replaces `recommend_style` / decision tree)

```python
# app/transition/selector.py
class TransitionSelector:
    def __init__(self, registry: dict[NeuralMixCrossfaderFX, FXStrategy] = FX_REGISTRY) -> None:
        self._registry = registry

    def select(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        context: SectionContext | None = None,
    ) -> NeuralMixCrossfaderFX:
        """Return the FX with highest applicability score."""
        return max(
            self._registry,
            key=lambda fx: self._registry[fx].applicability(score, features_a, features_b, context),
        )

    def build_recipe(self, ...) -> TransitionRecipe:
        fx = self.select(...)
        return self._registry[fx].build_recipe(...)
```

The registry is injected — `TransitionSelector` is testable with mock strategies.

### 3.4 `TransitionRecipe` and `RecipeStep` (unchanged dataclasses)

`recipe.py` keeps the existing `TransitionRecipe` and `RecipeStep` dataclasses. Their JSON serialisation/deserialisation stays as-is — DB column `transition_recipe_json` is unaffected.

### 3.5 `constants.py` (single source of magic numbers)

All numeric literals extracted from all deleted files go here, grouped by concern:

```python
# app/transition/constants.py
class ScoringWeights:
    BPM: float = 0.20
    HARMONIC: float = 0.12
    ENERGY: float = 0.18
    SPECTRAL: float = 0.20
    GROOVE: float = 0.15
    TIMBRAL: float = 0.15

class HardConstraints:
    MAX_BPM_DIFF: float = 10.0
    MAX_CAMELOT_DIST: int = 5
    MAX_ENERGY_GAP_LUFS: float = 6.0

class FXBarCounts:
    FADE: int = 16
    ECHO_OUT: int = 8
    VOCAL_SUSTAIN: int = 32
    HARMONIC_SUSTAIN: int = 32
    DRUM_SWAP: int = 4
    VOCAL_CUT: int = 4
    DRUM_CUT: int = 4

class ApplicabilityThresholds:
    # Per-FX decision thresholds — exact values extracted from
    # existing recipe_decision.py, weights.py, subgenre_rules.py during Step 1.
    DRUM_SWAP_MIN_GROOVE: float = 0.70
    ECHO_OUT_MAX_ENERGY: float = 0.50
    VOCAL_SUSTAIN_MIN_SPECTRAL: float = 0.55
    HARMONIC_SUSTAIN_MIN_HARMONIC: float = 0.55
    DRUM_CUT_MIN_GROOVE: float = 0.65
    VOCAL_CUT_MIN_SPECTRAL: float = 0.60
    FADE_FALLBACK: float = 0.30  # always applicable, lowest priority
```

### 3.6 `types.py` (enums, no logic)

```python
# app/transition/types.py
class Stem(StrEnum):
    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"

class StemAction(StrEnum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"

class TransitionIntent(IntEnum):
    MAINTAIN = 0
    RAMP_UP = 1
    COOL_DOWN = 2
    CONTRAST = 3
```

`NeuralMixCrossfaderFX` stays in `app/core/constants.py` — not moved.

---

## 4. Data Model Changes

### 4.1 DB migration

```sql
-- up
ALTER TABLE transitions DROP COLUMN transition_type;
ALTER TABLE transitions ADD COLUMN fx_type VARCHAR(30);

-- fx_type stores NeuralMixCrossfaderFX value, nullable (legacy rows stay null)
-- No data migration required: old transition_type was already nullable/dead
```

Alembic migration with full `downgrade()` (restore column, fill from `transition_recipe_json` if possible).

### 4.2 SQLAlchemy model update

`app/db/models/transition.py`:
- Remove: `transition_type: Mapped[str | None]`
- Add: `fx_type: Mapped[str | None]`  (stores `NeuralMixCrossfaderFX` value as string)

---

## 5. Consumer Changes

All imports updated — no logic changes in consumers:

| Consumer | Old import | New import |
|---|---|---|
| `services/set/scoring.py` | `from app.transition.style import recommend_style` | `from app.transition.selector import TransitionSelector` |
| `services/set/cheatsheet.py` | `from app.transition.recipe import TransitionRecipe` | unchanged |
| `services/candidate_service.py` | `from app.transition.scorer import TransitionScorer` | unchanged |
| `services/reasoning_service.py` | `from app.transition.scorer import TransitionScorer` | unchanged |
| `services/delivery_service.py` | `from app.transition.recipe import TransitionRecipe` | unchanged |
| `services/mix_point_service.py` | `from app.transition.section_context import SectionContext` | unchanged |
| `optimization/fitness.py` | `from app.transition.intent import infer_intent` | unchanged |
| `optimization/greedy.py` | `from app.transition.scorer import TransitionScorer` | unchanged |
| `optimization/genetic.py` | `from app.transition.scorer import TransitionScorer` | unchanged |

`recommend_style()` call sites in `set/scoring.py` and `set/cheatsheet.py` replaced with `TransitionSelector().select(score, features_a, features_b)`.

---

## 6. Public API (`__init__.py`)

```python
# app/transition/__init__.py
from app.transition.score import TransitionScore
from app.transition.scorer import TransitionScorer
from app.transition.selector import TransitionSelector
from app.transition.recipe import TransitionRecipe, RecipeStep
from app.transition.hard_constraints import check_hard_constraints
from app.transition.intent import infer_intent
from app.transition.section_context import SectionContext
from app.transition.math_helpers import bpm_distance, cosine_similarity

__all__ = [
    "TransitionScore",
    "TransitionScorer",
    "TransitionSelector",
    "TransitionRecipe",
    "RecipeStep",
    "check_hard_constraints",
    "infer_intent",
    "SectionContext",
    "bpm_distance",
    "cosine_similarity",
]
```

---

## 7. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `fx/base.py` + 7 FX files | Each FX encapsulates its own selection criteria and recipe logic |
| **Registry** | `fx/__init__.py` | Decouples selector from concrete strategies; O/C extensibility |
| **Facade** | `TransitionScorer` | Hides 6 component scorers behind a simple interface |
| **Template Method** | `FXStrategy.build_recipe()` | Common recipe structure, FX-specific stem/EQ steps overridden |
| **Dependency Injection** | `TransitionSelector(registry=...)` | Testable without global state |

---

## 8. Testing

### What changes

- `tests/test_transition/test_recipe_engine.py` → rewritten as `test_selector.py`
- `tests/test_transition/test_neural_mix.py` → rewritten testing individual `fx/*.py` strategies
- `tests/test_transition/test_subgenre_rules.py` → removed (logic absorbed into strategies)
- `tests/test_transition/` — new `test_fx_*.py` per strategy (applicability + build_recipe)
- `tests/test_domain/test_section_context.py` — unchanged
- DB migration test: verifies `fx_type` column present, `transition_type` absent

### What stays

- All component tests (`test_bpm.py`, `test_harmonic.py`, etc.) — unchanged
- `tests/test_domain/test_weights.py` → `test_constants.py` (renamed, same assertions)
- `tests/test_services/test_transition_scoring_p2.py` — update selector import only

---

## 9. Out of Scope

- `app/optimization/` — structure unchanged; only import updates in 3 files
- `app/db/repositories/` — no changes (no repository for transition scoring)
- Panel UI — no transition FX displayed in panel currently
- Audio stem separation (`separate_stems` tool) — separate feature, not wired to FX strategies

---

## 10. Implementation Order

1. Create `types.py` and `constants.py` (foundation, no dependencies)
2. Update `recipe.py` — clean up, remove broken `TransitionType` import
3. Create `fx/base.py` (abstract strategy)
4. Implement 7 FX strategies in `fx/*.py`
5. Create `fx/__init__.py` (registry)
6. Create `selector.py`
7. Update `scorer.py` — remove `recommend_style`, depend only on components + constants
8. Update `__init__.py` — clean public API
9. Delete 8 legacy files
10. Alembic migration (add `fx_type`, drop `transition_type`)
11. Update DB model
12. Update consumers (services + optimization)
13. Rewrite and add tests
14. `make check` — lint + typecheck + arch + tests
