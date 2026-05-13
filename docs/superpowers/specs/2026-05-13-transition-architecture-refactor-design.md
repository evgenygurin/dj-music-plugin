# Transition Architecture Refactor — Design Spec

> Дата: 2026-05-13
> Версия плагина: v1.4.0 → v1.5.0 (minor, internal refactor, no behaviour change)
> Branch префикс: `refactor/transition-arch-vN-…`
> Related:
> - [docs/transition-scoring.md](../../transition-scoring.md) — текущая документация scoring/picker/recipe
> - [docs/superpowers/specs/2026-04-08-transition-system-redesign.md](2026-04-08-transition-system-redesign.md) — предыдущий рефакторинг (Phase 1: вынесли weights/score/hard_constraints/components/section_context)
> - [tests/domain/transition/test_bulk_scorer_parity.py](../../../tests/domain/transition/test_bulk_scorer_parity.py) — существующий parity-guard, расширяется
> Authors: Claude (orchestrator), под делегатскими полномочиями пользователя для всех architectural-level decisions

---

## 0. TL;DR

`app/domain/transition/` за полгода вырос органически: после Phase 1 (апрель 2026) часть кода уже вынесена в отдельные модули, но **четыре фундаментальные боли** остались:

1. **`scorer.py` orchestrator (276 LOC) дублирует overlay-логику 3× и compose-логику 2×** через `_apply_section_overlay` и `_compute_score`.
2. **`neural_mix.py` (426 LOC) — god-module** на 4 SRP-нарушения: enums + weight matrices + 4 stem compat functions + Composite-классе + private helpers.
3. **`picker.py` (313 LOC) — if/elif каскад на 7 веток** + 5 inline-helper-функций (proxies) + lazy `build_recipe_for_pair` (recipe orchestration leaks из picker'а).
4. **`bulk_scorer.py` (660 LOC) — second source of truth** для каждого component'а scoring math, parity guard'ится тестом но drift detection требует параллельного reading двух файлов.

В сумме: добавить новый стиль (`FILTER_SWEEP`), новый scoring component, новое правило picker'а или новый WeightOverlay — каждый раз нужно править ядро (scorer/neural_mix/picker/builders/bulk_scorer). **Это нарушение OCP**.

Рефакторинг приводит подсистему к каноничной форме:

- Каждая операция (`ScoringComponent`, `HardConstraint`, `PickerRule`, `RecipeBuilder`, `WeightOverlay`, `VocalActivityDetector`) — **plug-in Strategy**, регистрируется явным module-level списком (explicit registry).
- `TransitionEvaluator` (новый orchestrator) — тонкий координатор, **зависит только от Protocol'ов**, никакой математики.
- `scoring/components/<name>.py` — co-located scalar + bulk implementations: один файл, два метода, один parity test.
- `picker/rules/<name>.py` — каждое правило отдельный файл, регистрируется в `DEFAULT_RULES` tuple, итерируется через CoR pipeline.
- `recipe/builders/<name>.py` — Template Method `BaseRecipeBuilder` с overridable hook'ами для preset-specific envelope.

**Расширение = новый файл + 1 строка в `__init__.py`**. Семантика и публичный API не меняются (golden tests guard'ят).

---

## 1. Scope

### In scope

- `app/domain/transition/` — целиком (16 файлов, 3 139 LOC).
- `app/handlers/transition_persist.py` — wiring через `TransitionScorerProtocol` (минимум правок).
- `app/handlers/set_version_build.py` — transition-часть (`_build_recipe_or_none` callsite).
- `app/tools/compute/transition_score_pool.py` — re-imports adjustment.
- `app/tools/compute/sequence_optimize.py` — fitness wiring через scorer.
- `app/tools/ui/ui_transition_score.py` / `ui_score_pool_matrix.py` — re-imports adjustment.
- `app/resources/transition.py` — re-imports adjustment.
- `app/domain/optimization/fitness.py` — `transition_quality` (signature не меняется).
- `app/server/lifespan.py` — DI provider switches `TransitionScorer` → `TransitionEvaluator` (через `TransitionScorerProtocol`).
- Tests: `tests/domain/transition/**` + `tests/handlers/test_transition_persist.py` + `tests/tools/compute/test_transition_score_pool.py` + `tests/resources/test_transition_resource.py`.

### Out of scope

- Audio analyzers (`app/audio/`) и features (`app/shared/features.py`).
- Repository / UoW / models (`app/repositories/transition*.py`, `app/models/transition.py`) — DB shape не меняется, includes `transitions.transition_recipe_json` column.
- Camelot wheel и subgenres registry (`app/domain/camelot/`, `app/shared/constants.py:TechnoSubgenre`).
- MCP server composition, middleware, visibility.
- Panel actions / REST routes — отдельная задача.
- Phase 3 stem separation (нужен `StemSeparator` analyzer, не существует). Architecture-side готова: `VocalActivityDetector` Protocol.
- Phase 2/3 calibration weights (новые overlays для DROP_TO_DROP / BREAKDOWN_OUT / BUILDUP_IN). Architecture-side готова: `WeightOverlay` Protocol.
- Новые присеты (`FILTER_SWEEP`, `LOOP_ROLL`, `STUTTER_FX`, `HARD_CUT`). Architecture-side готова: `RecipeBuilder` Protocol + acceptance test (раздел 6).
- Per-subgenre scoring profiles (Phase 2 ROADMAP). Architecture-side готова: `ComponentWeightProfile` Strategy.

---

## 2. Goals / Non-Goals

### Goals

1. **OCP compliance.** Добавление нового scoring component / picker rule / recipe builder / weight overlay / vocal detector = ровно один новый файл + 1 строка в `__init__.py` registry. Доказывается **acceptance test** (раздел 6): «реализовать synthetic `FILTER_SWEEP` builder одним новым файлом без правок ядра».
2. **SRP за каждый класс/функцию.** Никакой класс не делает math + composition + serialization одновременно.
3. **DRY** — устранить дубликат `_apply_section_overlay` (3×) и `_compute_score` (2×) в `scorer.py`. Удалить `INTENT_WEIGHT_MODIFIERS` дубликат (есть в `intent.py` И в `weights.py`).
4. **Public API заморожен на 100%.** Все 21 имя из текущего `app/domain/transition/__init__.py:__all__` остаются работоспособны. Adapter-функции/классы.
5. **Behaviour identical.** Golden tests на 3 уровнях (scalar score / recipe envelopes / bulk parity) — байт-в-байт совпадение, tolerance 1e-9.
6. **Scalar + bulk co-located.** `scoring/components/<name>.py` экспортирует и `score(a, b)`, и `score_pairs(fa, ia, ib)` под единым Protocol. `bulk_scorer.py` исчезает как монолит, его функциональность распределяется по компонентам.
7. **Mypy strict + ruff clean + import-linter happy.** Все Protocol'ы — runtime-checkable где имеет смысл.
8. **Документация обновлена.** [docs/transition-scoring.md](../../transition-scoring.md) — секции "Module Layout" + "Extension Points". Новый файл [docs/transition-architecture.md](../../transition-architecture.md) — диаграмма зависимостей + GoF patterns.

### Non-Goals

- **Не переписываем с нуля.** Семантика, формулы, magic numbers (после миграции в один файл) — без изменений.
- **Не меняем `transitions` DB schema**, включая `transition_recipe_json` JSON shape.
- **Не добавляем новые dependencies** в `pyproject.toml`. Pure Python + numpy.
- **Не калибруем weights/thresholds.** Это Phase 2/3 ROADMAP.
- **Не пишем новые presets.** Только инфраструктура для их добавления.
- **Не делаем формальный Specification pattern** (and_/or_/not_ composition over hard constraints). Strategy + Chain покрывает 3 ortogонал гейта без overhead.
- **Не добавляем Visitor pattern.** Нет ortogональных операций над фиксированной структурой → YAGNI.
- **Не добавляем Decorator на WeightedScoringComponent.** Composite уже хранит `list[tuple[Component, weight]]`.

---

## 3. Decisions Matrix (autonomous resolutions)

| # | Open question | Decision | Rationale |
|---|---|---|---|
| D1 | `bulk_scorer.py` — что с ним делать | **Co-locate scalar + bulk per component.** Каждый `scoring/components/<name>.py` имплементирует `ScoringComponent` Protocol с двумя методами: `score(a, b) -> float` и `score_pairs(fa, ia, ib) -> FloatArr`. Старый `bulk_scorer.py` распределяется по компонентам; module-level helpers (`FeatureArrays`, `extract_feature_arrays`, `_CAMELOT_DISTANCE`, `_bpm_distance_bulk`, `_cosine_similarity_bulk`) переезжают в `scoring/bulk/arrays.py` + `scoring/bulk/kernels.py`. | Один источник правды per component, side-by-side maintenance, drift detection через parity tests. |
| D2 | Сколько GoF паттернов | **5 из 7.** In: Strategy (компоненты, правила, overlays, detectors), Composite (`CompositeScorer`), Registry/Factory (explicit lists в `__init__.py`), Template Method (`BaseRecipeBuilder` с `_build_a_envelope`/`_build_b_envelope`/`_build_fx_events` hooks), Chain of Responsibility (picker pipeline + hard-constraint chain). Out: Visitor (нет ortogональных операций), Decorator (Composite уже хранит weights). | Применяем ровно те паттерны, что снимают конкретную боль. YAGNI на остальные. |
| D3 | Registry: decorator-based vs explicit list | **Explicit module-level tuple.** В `scoring/components/__init__.py`: `DEFAULT_COMPONENTS: tuple[ScoringComponent, ...] = (BpmComponent(), EnergyComponent(), …)`. Аналог для `picker/rules/__init__.py`, `recipe/builders/__init__.py`, `constraints/specs/__init__.py`, `picker/proxies/__init__.py`. | Decorator-based registry создаёт import-time side effects, ломает tree-shaking, плохо дружит с mypy strict (runtime registry type стирается), хуже unit-testable. Explicit list — Python idiom, читается линейно. OCP не страдает: новый файл + 1 строка = новый компонент. |
| D4 | `_vocal_active` под будущий stem separator | **Отдельный `picker/proxies/vocal_activity.py` + `VocalActivityDetector` Protocol.** Default impl = `SpectralVocalActivityDetector` (текущие 3 spectral proxy). Будущая `StemVocalActivityDetector(stem_provider)` добавится одним файлом. DI через picker конструктор. | Protocol изолирует "как мы определяем вокал" от "что делать когда вокал найден". |
| D5 | `scorer.py` 3 entry points | **Унификация в один `TransitionEvaluator.evaluate(pair, *, intent?, intents?, section_context?, pre_distances?)`.** Старые методы (`score`, `score_all_intents`, `score_with_candidates`) — тонкие backward-compat adapters в `TransitionScorer` proxy-классе. | Снимает 80 строк дубликата (`_apply_section_overlay` × 3, `_compute_score` × 2). Public API сохраняется. |
| D6 | Hard constraints: Strategy vs Specification | **Strategy + Chain of Responsibility.** 3 файла в `constraints/specs/`: `bpm_difference.py`, `camelot_distance.py`, `energy_gap.py`. `HardConstraintChain` итерирует, first-match-wins. | Specification — DDD-стиль с `and_/or_/not_` composition; у нас 3 ortogональных гейта. Strategy + Chain выражает то же без abstract overhead. |
| D7 | Weight overlays (intent + section-pair) | **`WeightOverlay` Protocol + Chain.** `IntentOverlay(intent)`, `SectionOverlay(ctx)`. Применяются последовательно к base weights, последний делает renormalisation. | Сейчас overlay-логика дублирована в 3 методах scorer'а. Вынос в Strategy + Chain делает overlays plug-in (Phase 3 DROP_TO_DROP / BREAKDOWN_OUT добавятся новыми overlay'ями без правок ядра). |
| D8 | Public API surface | **Заморожен на 100%.** Все имена из текущего `__all__` (18 шт.) остаются. Internal API (private function names типа `_apply_section_overlay`, `_weighted_average`, `_energy_bias_modifier`) могут переезжать без deprecation. | Без этого нельзя гарантировать "no behaviour change". |
| D9 | Golden tests | **3 уровня**: (a) scalar score parity — 20 представительных пар → snapshot 6 component values + overall, 1e-9 tolerance; (b) recipe parity — все 7 presets при bars ∈ {16, 32, 64} → per-keyframe snapshot; (c) bulk parity — расширение существующего на N×N матрицу × 4 intents × DRUM_ONLY context. JSON snapshots в `tests/domain/transition/_golden/*.json`. | Защита от любого case'а: scoring math, recipe envelopes, GA hot path. JSON — diff-friendly, читаемо в PR review. |
| D10 | Deprecation re-exports | **Старые имена остаются как re-exports до v2.0.** В v2.0 — `DeprecationWarning`. Удаление в v3.0. | Soft deprecation, никто не сломается включая внешние интеграции. |
| D11 | `INTENT_WEIGHT_MODIFIERS` дубликат | **`intent.py` — source of truth, `weights.py` чистится от INTENT_*.** Также все per-intent dicts сделаны frozen (immutable tuple-of-pairs или `frozendict` сурогат). | Дубликат был артефактом v1.3.1 переименования. |
| D12 | NeuralMix enums и weight matrices | **`enums.py` (NeuralMixStem, NeuralMixTransition), `neural_mix/weight_matrix.py` (TRANSITION_STEM_WEIGHTS, TRANSITION_ENERGY_BIAS), `neural_mix/composite.py` (NeuralMixScorer = Composite). 4 stem compat functions переезжают в `scoring/components/{drums,bass,harmonics,vocals}.py`. | Разделяет `neural_mix.py` god-module на 6 файлов по SRP. |

---

## 4. Architecture

### 4.1 Target directory structure

```text
app/domain/transition/
├── __init__.py                     # Frozen public API (21 names re-exported)
├── api.py                          # Protocols: ScoringComponent, HardConstraint,
│                                   #            WeightOverlay, PickerRule,
│                                   #            VocalActivityDetector,
│                                   #            HarmonicMotifDetector,
│                                   #            RecipeBuilder, TransitionEvaluatorProtocol
├── enums.py                        # NeuralMixStem, NeuralMixTransition,
│                                   # TransitionIntent, SubgenrePairType, SectionPairClass
├── score.py                        # TransitionScore frozen dataclass (output type)
├── orchestrator.py                 # TransitionEvaluator (DI wires Protocols) + legacy
│                                   # TransitionScorer adapter (frozen public API)
│
├── kernels/                        # Reusable math primitives — pure numpy / pure stdlib
│   ├── __init__.py
│   ├── bpm_distance.py             # bpm_distance(a, b), bpm_distance_bulk(a, b)
│   ├── camelot_lookup.py           # _CAMELOT_DISTANCE table + scalar/bulk helpers
│   ├── cosine.py                   # cosine_similarity scalar + bulk
│   ├── gauss.py                    # gauss_similarity(x, sigma) scalar + bulk
│   └── correlation.py              # correlation scalar (legacy export)
│
├── scoring/
│   ├── __init__.py                 # DEFAULT_COMPONENTS: tuple[ScoringComponent, ...]
│   ├── composite.py                # CompositeScorer (applies WeightOverlay chain, sums)
│   ├── components/                 # One file per component, scalar + bulk co-located
│   │   ├── __init__.py
│   │   ├── bpm.py                  # BpmComponent.score / score_pairs
│   │   ├── energy.py               # EnergyComponent
│   │   ├── drums.py                # DrumsComponent (Neural Mix DRUMS stem compat)
│   │   ├── bass.py                 # BassComponent (Neural Mix BASS stem compat)
│   │   ├── harmonics.py            # HarmonicsComponent (HARMONICS stem)
│   │   └── vocals.py               # VocalsComponent (VOCALS stem)
│   ├── overlays/                   # WeightOverlay strategies
│   │   ├── __init__.py             # DEFAULT_OVERLAY_CHAIN: tuple[WeightOverlay, ...]
│   │   ├── intent.py               # IntentOverlay (per-intent base weights)
│   │   ├── section_pair.py         # SectionPairOverlay (DRUM_ONLY + identity for others)
│   │   └── renormalise.py          # RenormaliseOverlay (terminal, sums to 1.0)
│   └── bulk/                       # Shared bulk-only helpers
│       ├── __init__.py
│       ├── arrays.py               # FeatureArrays + extract_feature_arrays
│       └── stem_weight_matrix.py   # TRANSITION_STEM_WEIGHTS to numpy lookup
│
├── constraints/
│   ├── __init__.py                 # DEFAULT_CONSTRAINTS: tuple[HardConstraint, ...]
│   ├── chain.py                    # HardConstraintChain.check(a, b, pre) → Reject | None
│   └── specs/
│       ├── __init__.py
│       ├── bpm_difference.py       # BpmDifferenceSpec
│       ├── camelot_distance.py     # CamelotDistanceSpec
│       └── energy_gap.py           # EnergyGapSpec
│
├── neural_mix/                     # Neural-Mix-specific composite (best-of-7)
│   ├── __init__.py
│   ├── weight_matrix.py            # TRANSITION_STEM_WEIGHTS + TRANSITION_ENERGY_BIAS
│   ├── energy_bias.py              # energy_bias_modifier scalar + bulk
│   ├── score_dataclass.py          # NeuralMixScore (legacy result, still exported)
│   └── composite.py                # NeuralMixScorer = best-transition argmax over stems
│
├── picker/
│   ├── __init__.py                 # DEFAULT_RULES: tuple[PickerRule, ...] (CoR order)
│   ├── api.py                      # PickerDecision frozen dataclass
│   ├── pipeline.py                 # PickerPipeline.pick(score, fa, fb, ctx) → Decision
│   ├── proxies/                    # Auxiliary signal detectors (Strategy)
│   │   ├── __init__.py
│   │   ├── vocal_activity.py       # SpectralVocalActivityDetector (3 proxies)
│   │   ├── harmonic_motif.py       # HarmonicMotifDetector
│   │   └── camelot_compatibility.py# CamelotCompatibilityCheck
│   └── rules/                      # One file per rule, CoR-iterated
│       ├── __init__.py
│       ├── hard_reject_rescue.py   # Rule 1
│       ├── drum_only_section.py    # Rule 2
│       ├── vocal_active.py         # Rule 3
│       ├── harmonic_sustain.py     # Rule 4
│       ├── energy_drop_to_slam.py  # Rule 5
│       ├── ambient_or_cooldown.py  # Rule 6
│       └── default_echo_out.py     # Rule 7 (terminal)
│
├── recipe/
│   ├── __init__.py                 # DEFAULT_BUILDERS: dict[NeuralMixTransition,
│   │                               #                       RecipeBuilder]
│   ├── api.py                      # RecipeBuilder Protocol + KeyframeBundle alias
│   ├── model.py                    # NeuralMixRecipe + StemKeyframe + MuteFXEvent
│   │                               # (frozen dataclasses, no logic)
│   ├── serialization.py            # to_json / from_json (extracted from model.py)
│   ├── constants.py                # LEVEL_SILENT, LEVEL_UNITY, DEFAULT_TRANSITION_BARS,
│   │                               # MuteFXTrigger enum, Deck Literal
│   ├── factory.py                  # RecipeBuilderRegistry.build(transition, …)
│   ├── orchestrator.py             # build_recipe_for_pair (picker → builder dispatch)
│   ├── envelopes/                  # Reusable envelope helpers (Template Method hooks)
│   │   ├── __init__.py
│   │   ├── linear_fade.py          # Linear ramp helpers
│   │   ├── hold_then_fade.py       # _hold + ramp combos
│   │   ├── kill_with_echo.py       # Sequential stem kill + echo FX
│   │   └── enter_ramp.py           # B-side entry helpers
│   └── builders/                   # One builder per NeuralMixTransition
│       ├── __init__.py
│       ├── base.py                 # BaseRecipeBuilder (Template Method)
│       │                           # Hooks: _build_a_envelope, _build_b_envelope,
│       │                           #        _build_fx_events
│       ├── fade.py                 # FadeRecipeBuilder
│       ├── echo_out.py             # EchoOutRecipeBuilder
│       ├── vocal_sustain.py        # VocalSustainRecipeBuilder
│       ├── harmonic_sustain.py     # HarmonicSustainRecipeBuilder
│       ├── drum_swap.py            # DrumSwapRecipeBuilder
│       ├── vocal_cut.py            # VocalCutRecipeBuilder
│       └── drum_cut.py             # DrumCutRecipeBuilder
│
└── context/
    ├── __init__.py
    ├── section.py                  # SectionContext + section_pair_class logic
    ├── subgenre.py                 # SubgenrePairType + classify_pair + clamp_bars
    └── intent.py                   # infer_intent + _TEMPLATE_PHASE_TABLE
```

**File count**: 16 → ~55 files. Average file size: ~50 LOC (vs current ~200 LOC). Сравни: `picker.py` 313 LOC → 7 rule files × ~30 LOC + pipeline 30 LOC + 3 proxies × ~25 LOC.

### 4.2 Public API surface (frozen)

`app/domain/transition/__init__.py` после рефакторинга re-exports **точно те же 21 имя** (плюс новые, опционально):

```python
# Frozen — these imports MUST keep working
from app.domain.transition import (
    # Score result + scoring orchestrator
    TransitionScore,                  # → score.py (unchanged shape)
    TransitionScorer,                 # → orchestrator.py (legacy adapter)

    # Neural Mix primitives
    NeuralMixStem,                    # → enums.py
    NeuralMixTransition,              # → enums.py
    NeuralMixScore,                   # → neural_mix/score_dataclass.py
    NeuralMixScorer,                  # → neural_mix/composite.py

    # Recipe primitives
    NeuralMixRecipe,                  # → recipe/model.py
    StemKeyframe,                     # → recipe/model.py
    MuteFXEvent,                      # → recipe/model.py
    MuteFXTrigger,                    # → recipe/constants.py
    LEVEL_SILENT, LEVEL_UNITY,        # → recipe/constants.py
    DEFAULT_TRANSITION_BARS,          # → recipe/constants.py
    build_recipe,                     # → recipe/factory.py

    # Picker + decision
    PickerDecision,                   # → picker/api.py
    pick_neural_mix,                  # → picker/pipeline.py (functional adapter)
    build_recipe_for_pair,            # → recipe/orchestrator.py

    # Context
    SectionContext,                   # → context/section.py

    # Math helpers
    bpm_distance,                     # → kernels/bpm_distance.py
    correlation,                      # → kernels/correlation.py
    cosine_similarity,                # → kernels/cosine.py
)
```

**New optional exports** (additive, for power users):

```python
from app.domain.transition import (
    TransitionEvaluator,              # The new orchestrator (DI-wired)
    ScoringComponent,                 # Protocol for adding components
    PickerRule,                       # Protocol for adding rules
    RecipeBuilder,                    # Protocol for adding builders
    WeightOverlay,                    # Protocol for adding overlays
    VocalActivityDetector,            # Protocol for stem separator integration
    DEFAULT_COMPONENTS,               # Reference tuple for inspection
    DEFAULT_RULES,
    DEFAULT_BUILDERS,
)
```

### 4.3 Dependency rule

```text
api.py (Protocols)        ← root, no imports from domain.transition
  ↑
enums.py                  ← no internal imports
kernels/                  ← only stdlib + numpy
  ↑
recipe/model.py           ← enums + recipe/constants
context/                  ← enums + shared.constants
  ↑
constraints/              ← enums + kernels + score
scoring/components/       ← api + kernels + scoring/bulk/arrays + shared.features
scoring/overlays/         ← api + context
scoring/composite.py      ← api + scoring/{components,overlays}
neural_mix/               ← api + enums + scoring/components (re-uses 4 stem scorers)
recipe/builders/          ← api + recipe/{model,constants,envelopes} + enums
recipe/factory.py         ← api + recipe/builders
recipe/orchestrator.py    ← api + recipe/factory + picker/api
picker/proxies/           ← api + shared.features
picker/rules/             ← api + picker/proxies + enums + score
picker/pipeline.py        ← api + picker/rules
orchestrator.py           ← api + scoring + constraints + context + neural_mix
```

Cycle-free. Verified by import-linter (add a new contract — раздел 5.3).

### 4.4 Core protocols

```python
# app/domain/transition/api.py

from typing import Protocol, runtime_checkable
import numpy.typing as npt

FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]

@runtime_checkable
class ScoringComponent(Protocol):
    """Strategy: one component of the weighted scoring formula.

    Each component carries its own weight, its own feature dependencies,
    and its own scalar/bulk implementations. Components are composed by
    CompositeScorer.
    """

    name: str  # "bpm", "energy", "drums", "bass", "harmonics", "vocals"
    default_weight: float

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float: ...

    def score_pairs(
        self, fa: FeatureArrays, ia: IntArr, ib: IntArr,
    ) -> FloatArr: ...

@runtime_checkable
class HardConstraint(Protocol):
    """Strategy: one hard-reject gate. Chain of constraints, first-match-wins."""

    name: str  # "bpm_difference", "camelot_distance", "energy_gap"

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> str | None:
        """Return rejection reason string, or None if pass."""
        ...

    def check_bulk(
        self, fa: FeatureArrays, ia: IntArr, ib: IntArr,
    ) -> BoolArr:
        """Vector of per-pair violation booleans."""
        ...

@runtime_checkable
class WeightOverlay(Protocol):
    """Strategy: transformer of base weights given context.

    Overlays are applied as a chain. The terminal RenormaliseOverlay
    ensures the resulting weights sum to 1.0.
    """

    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]: ...

@runtime_checkable
class VocalActivityDetector(Protocol):
    """Strategy: detect whether a track has vocal-active sections.

    Default impl uses 3 spectral proxies (SpectralVocalActivityDetector).
    Phase 3 stem separation will add StemVocalActivityDetector(stem_provider).
    """

    def is_active(self, t: TrackFeatures) -> bool: ...

    def is_low(self, t: TrackFeatures) -> bool: ...

    def data_missing(self, t: TrackFeatures) -> bool: ...

@runtime_checkable
class HarmonicMotifDetector(Protocol):
    """Strategy: detect harmonic-motif tracks for HARMONIC_SUSTAIN picker rule."""

    def is_motif(self, t: TrackFeatures) -> bool: ...

@runtime_checkable
class PickerRule(Protocol):
    """Strategy: one branch of the picker decision tree.

    Rules are iterated as Chain of Responsibility — first non-None return wins.
    """

    name: str
    confidence: float  # picker confidence if this rule fires

    def evaluate(
        self,
        score: TransitionScore,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        section_context: SectionContext | None,
        subgenre_pair: SubgenrePairType | None,
        intent: TransitionIntent | None,
    ) -> PickerDecision | None: ...

@runtime_checkable
class RecipeBuilder(Protocol):
    """Strategy: one Neural Mix preset's stem-keyframe envelope builder.

    Concrete builders extend BaseRecipeBuilder (Template Method) but can
    also implement RecipeBuilder directly for full control.
    """

    transition: NeuralMixTransition

    def build(self, bars: int) -> KeyframeBundle: ...

class TransitionEvaluatorProtocol(Protocol):
    """The orchestrator surface — what callers and DI containers depend on."""

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
    ) -> TransitionScore: ...

    def evaluate_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent],
        *,
        section_context: SectionContext | None = None,
    ) -> dict[TransitionIntent, TransitionScore]: ...

    def evaluate_pairs(
        self,
        tracks: Sequence[TrackFeatures],
        pairs: Sequence[tuple[int, int]],
        intents: Iterable[TransitionIntent],
        *,
        section_context: SectionContext | None = None,
    ) -> dict[tuple[int, int, str], float]: ...  # bulk path
```

### 4.5 TransitionScorer adapter

Сохраняет signature 1-в-1 для backward-compat. Внутри проксирует на `TransitionEvaluator`.

```python
# app/domain/transition/orchestrator.py

class TransitionScorer:
    """Legacy adapter — preserved for backward-compat (v1.5.x → v2.0)."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._evaluator = TransitionEvaluator(
            components=DEFAULT_COMPONENTS,
            weight_overlay_chain=DEFAULT_OVERLAY_CHAIN,
            hard_constraint_chain=DEFAULT_HARD_CONSTRAINT_CHAIN,
            neural_mix_composite=NeuralMixScorer(),
            base_weights=weights,
        )

    def score(self, from_t, to_t, *, intent=None, section_context=None):
        return self._evaluator.evaluate(
            from_t, to_t, intent=intent, section_context=section_context,
        )

    def score_all_intents(self, from_t, to_t, intents=None, *, section_context=None):
        return self._evaluator.evaluate_intents(
            from_t, to_t,
            intents if intents is not None else _ALL_INTENTS,
            section_context=section_context,
        )

    def score_with_candidates(self, from_t, to_t,
                              candidate_bpm_distance=None,
                              candidate_key_distance=None,
                              candidate_energy_delta=None, *,
                              section_context=None):
        return self._evaluator.evaluate(
            from_t, to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
            section_context=section_context,
        )
```

`fitness.transition_quality` продолжает использовать `TransitionScorer`. `app/server/lifespan.py` тоже. Внешние интеграции — без правок.

---

## 5. GoF Pattern Mapping

Каждый паттерн с пояснением **зачем именно тут**.

### 5.1 Strategy (везде)

**Применён в**: `ScoringComponent`, `HardConstraint`, `WeightOverlay`, `PickerRule`, `RecipeBuilder`, `VocalActivityDetector`, `HarmonicMotifDetector`.

**Зачем**: каждое из этих — самостоятельное правило/алгоритм с собственными зависимостями. Заменяемость требуется для:
- Тестирования (mock рулов в test_picker_pipeline).
- Расширения (Phase 2 per-subgenre profiles → новые ComponentWeightProfile).
- Будущей замены (`SpectralVocalActivityDetector` → `StemVocalActivityDetector`).

### 5.2 Composite (`CompositeScorer`)

**Применён в**: `scoring/composite.py`.

**Зачем**: `CompositeScorer` хранит `tuple[ScoringComponent, ...]` + chain of `WeightOverlay`'s. Применяет компоненты, аккумулирует overall = `Σ component.score(...) * overlay_chain(weights)[component.name]`.

Альтернатива (Decorator на WeightedScoringComponent) отвергнута: Composite уже хранит `(component, weight)` пары через `default_weight` поле + overlay chain. Decorator — лишний слой.

### 5.3 Chain of Responsibility (×2: hard constraints + picker)

**Применён в**: `constraints/chain.py:HardConstraintChain`, `picker/pipeline.py:PickerPipeline`.

**Зачем**: оба — first-match-wins цепочки. Hard constraints: BPM diff → Camelot dist → energy gap → pass. Picker: hard-reject-rescue → drum-only → vocal-active → harmonic-sustain → energy-drop → ambient-or-cooldown → default-echo-out.

Текущая реализация — if/elif каскад. CoR декомпозирует на per-rule файлы.

### 5.4 Template Method (`BaseRecipeBuilder`)

**Применён в**: `recipe/builders/base.py`.

**Зачем**: 7 presets имеют идентичную форму (бары → KeyframeBundle), но preset-specific envelope shape. Сейчас `_sustain` и `_cut` — shared helpers между парами presets (VOCAL_SUSTAIN/HARMONIC_SUSTAIN, VOCAL_CUT/DRUM_CUT) — это классический Template Method.

```python
class BaseRecipeBuilder(ABC):
    transition: ClassVar[NeuralMixTransition]
    mute_fx_trigger: ClassVar[MuteFXTrigger | None] = None

    def build(self, bars: int) -> KeyframeBundle:
        a_kfs = self._build_a_envelope(bars)
        b_kfs = self._build_b_envelope(bars)
        fx = self._build_fx_events(bars)
        return tuple(a_kfs + b_kfs), fx

    @abstractmethod
    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]: ...

    @abstractmethod
    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]: ...

    def _build_fx_events(self, bars: int) -> tuple[MuteFXEvent, ...]:
        return ()  # default: no FX
```

Конкретные builders переопределяют 2-3 метода. VOCAL_SUSTAIN и HARMONIC_SUSTAIN могут наследовать ещё один промежуточный класс `_SustainBuilder` который делит `_sustain` логику с параметром `sustained_stem`.

### 5.5 Factory Method / Registry (×3)

**Применён в**: `recipe/factory.py:RecipeBuilderRegistry`, `scoring/components/__init__.py:DEFAULT_COMPONENTS`, `picker/rules/__init__.py:DEFAULT_RULES`.

**Зачем**: создать right объект по enum (`NeuralMixTransition → RecipeBuilder`) или по позиции в default chain. Explicit list (D3).

```python
# recipe/factory.py
DEFAULT_BUILDERS: dict[NeuralMixTransition, RecipeBuilder] = {
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
    builders: Mapping[NeuralMixTransition, RecipeBuilder] | None = None,
    **metadata: Any,
) -> NeuralMixRecipe:
    """Public adapter: same signature as today's build_recipe."""
    if bars <= 0:
        raise ValueError(f"bars must be positive, got {bars}")
    builder = (builders or DEFAULT_BUILDERS)[transition]
    keyframes, fx_events = builder.build(bars)
    return NeuralMixRecipe(transition=transition, bars=bars,
                           keyframes=keyframes, fx_events=fx_events,
                           **metadata)
```

### 5.6 Что НЕ применяем

| Pattern | Why rejected |
|---|---|
| Visitor | Нет ortogональных операций над фиксированной структурой. У нас одна структура (`TransitionScore`) и одна операция (compute) — Visitor добавит лишнюю абстракцию. Serialization recipe → JSON это `.to_json()` method, не Visitor. |
| Specification (DDD) | Только 3 hard constraints, нет нужды в `and_/or_/not_` composition. Strategy + Chain достаточны. |
| Decorator (WeightedScoringComponent) | Composite + WeightOverlay chain уже делают то же без лишнего слоя. |
| Builder (NeuralMixRecipeBuilder sugar) | `NeuralMixRecipe` — frozen dataclass с tuple keyframes, уже чистый. Per-preset builders — это `RecipeBuilder` Strategy, не Builder pattern в GoF смысле (тот про пошаговую конструкцию с одним общим типом). |
| Observer | Нет event-driven flows в scoring/picker/recipe. |
| Adapter | Только в одном месте (`TransitionScorer` → `TransitionEvaluator`), не паттерн а просто backward-compat wrapper. |

---

## 6. Acceptance test — OCP demonstration

Один из критериев DoD: **новый preset добавляется одним новым файлом без правок ядра**. Реализуем synthetic test `tests/domain/transition/test_extension_filter_sweep.py`:

```python
"""OCP demonstration: adding FILTER_SWEEP preset via one new file.

Note: FILTER_SWEEP is NOT shipped in v1.5.0. This test creates a
local synthetic NeuralMixTransition member equivalent solely to
demonstrate that the registries (recipe/scoring/picker) accept a
plug-in extension without touching the core orchestrator, scorer,
or picker pipeline.
"""

from app.domain.transition.api import RecipeBuilder
from app.domain.transition.recipe.builders.base import BaseRecipeBuilder
from app.domain.transition.recipe.factory import build_recipe, DEFAULT_BUILDERS
from app.domain.transition.enums import NeuralMixTransition

class FilterSweepRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.FADE  # synthetic alias

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        # ... synthetic filter-sweep envelope
        ...

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        ...

def test_new_builder_plugs_in_without_core_edits():
    custom_builders = {**DEFAULT_BUILDERS, NeuralMixTransition.FADE: FilterSweepRecipeBuilder()}
    recipe = build_recipe(NeuralMixTransition.FADE, bars=32, builders=custom_builders)
    assert isinstance(recipe, NeuralMixRecipe)
    assert all(kf.bar <= 32 for kf in recipe.keyframes)
    # Core untouched: signature of build_recipe accepted custom builders dict
```

Аналогичные acceptance tests для:
- `test_extension_custom_picker_rule.py` — добавить новое правило в picker chain через `PickerPipeline(rules=DEFAULT_RULES + (CustomRule(),))`.
- `test_extension_custom_overlay.py` — добавить новый WeightOverlay в chain.
- `test_extension_custom_component.py` — добавить новый scoring component в Composite.

Все 4 тестируют что **сигнатуры registries / pipelines / composites принимают user-provided collections**. Это формальное доказательство OCP-compliance.

---

## 7. Migration Phases (PR sequence)

Каждый PR — независимо `make check`-clean. Идём по dependency order (нижние слои → верхние).

### PR 0 — Golden tests baseline

**Branch**: `refactor/transition-arch-v0-golden`

**Цель**: зафиксировать текущее поведение перед любым рефакторингом.

**Файлы**:
- `tests/domain/transition/test_golden_scoring.py` — 20 представительных пар, snapshot 6 component values + overall, snapshot JSON в `tests/domain/transition/_golden/scoring.json`.
- `tests/domain/transition/test_golden_recipes.py` — все 7 presets × bars ∈ {16, 32, 64} → per-keyframe + per-fx-event snapshot, JSON в `_golden/recipes_<preset>.json`.
- `tests/domain/transition/test_golden_picker.py` — 30 представительных decision scenarios (vocal-active A + low B, drum-only DRUM_ONLY, hard reject, ...) → snapshot picker decision.
- `tests/domain/transition/test_golden_overlays.py` — для всех 4 intents × 5 SectionPairClass values × DEFAULT_WEIGHTS → snapshot resulting weights dict.
- Расширение существующего `test_bulk_scorer_parity.py` — добавить scenarios с DRUM_ONLY context (сейчас не покрыт).

**No code changes**, только тесты. После PR 0 любой regression в любом из 4 уровней будет caught.

**Acceptance**: все 4 новых файла зелёные. Старые тесты не тронуты.

### PR 1 — Protocols + new layout skeleton

**Branch**: `refactor/transition-arch-v1-protocols`

**Цель**: создать новую структуру каталогов с пустыми модулями + Protocol definitions. Старые модули остаются работать (re-exports не меняются).

**Файлы**:
- `app/domain/transition/api.py` — все 8 Protocol'ов.
- `app/domain/transition/enums.py` — re-exports `NeuralMixStem`, `NeuralMixTransition` из `neural_mix.py`; новый `TransitionIntent`, `SubgenrePairType`, `SectionPairClass` (re-exports пока).
- `app/domain/transition/kernels/__init__.py` + 5 stub файлов — re-exports из `math_helpers.py`, `bulk_scorer.py:_camelot_distance_table`, etc.
- `app/domain/transition/scoring/__init__.py` + skeleton modules.
- `app/domain/transition/picker/__init__.py` + skeleton.
- `app/domain/transition/recipe/__init__.py` + skeleton.
- `app/domain/transition/constraints/__init__.py` + skeleton.
- `app/domain/transition/context/__init__.py` + skeleton.
- `app/domain/transition/neural_mix/__init__.py` + skeleton.

**No logic moves yet**. Только структура + Protocols + re-exports.

**Acceptance**:
- Все Protocol'ы определены с runtime-checkable.
- Старый `app/domain/transition/__init__.py` остаётся источником истины.
- `make check` зелёный.
- Все golden tests из PR 0 зелёные.

### PR 2 — Constraints migration

**Branch**: `refactor/transition-arch-v2-constraints`

**Цель**: разбить `hard_constraints.py:check_hard_constraints` на 3 Spec файла + Chain.

**Файлы созданы**:
- `constraints/specs/bpm_difference.py:BpmDifferenceSpec`
- `constraints/specs/camelot_distance.py:CamelotDistanceSpec`
- `constraints/specs/energy_gap.py:EnergyGapSpec`
- `constraints/chain.py:HardConstraintChain.check(a, b, pre=...) -> TransitionScore | None`
- `constraints/__init__.py:DEFAULT_CONSTRAINTS: tuple[HardConstraint, ...]`

**Файлы изменены**:
- `app/domain/transition/hard_constraints.py` — становится тонким adapter'ом: `check_hard_constraints(a, b, **kw) = HardConstraintChain(DEFAULT_CONSTRAINTS).check(a, b, **kw)`.
- Аналог для `bulk_scorer.py:hard_reject_mask_bulk` — adapter поверх `HardConstraintChain.check_bulk`.

**Tests**: новый `tests/domain/transition/constraints/test_*.py` per-spec. Существующий `test_hard_constraints.py` не меняется и продолжает проходить.

### PR 3 — Scoring components + Composite + Overlays

**Branch**: `refactor/transition-arch-v3-scoring`

**Цель**: главный structural PR. Распределение `neural_mix.py` + `scorer.py` + `bulk_scorer.py` + `components/` по новой структуре.

**Файлы созданы**:
- `scoring/components/{bpm,energy,drums,bass,harmonics,vocals}.py` — каждый имплементирует `ScoringComponent` Protocol. Scalar + bulk co-located. Math идентична (1-в-1 copy from current `components/bpm.py`, `components/energy.py`, `neural_mix.py:score_drums_compat`, etc, plus their bulk counterparts).
- `scoring/composite.py:CompositeScorer` — applies WeightOverlay chain, sums weighted components.
- `scoring/overlays/{intent,section_pair,renormalise}.py` — 3 overlay strategies.
- `scoring/overlays/__init__.py:DEFAULT_OVERLAY_CHAIN`.
- `scoring/bulk/arrays.py` — `FeatureArrays` + `extract_feature_arrays` (из `bulk_scorer.py`).
- `scoring/bulk/stem_weight_matrix.py` — `_stem_weight_matrix()` helper.
- `kernels/{bpm_distance,camelot_lookup,cosine,gauss}.py` — реальные имплементации, не re-exports.

**Файлы изменены**:
- `neural_mix.py` → распадается на:
  - `neural_mix/weight_matrix.py` (TRANSITION_STEM_WEIGHTS + TRANSITION_ENERGY_BIAS).
  - `neural_mix/energy_bias.py` (`energy_bias_modifier` scalar + bulk).
  - `neural_mix/score_dataclass.py` (NeuralMixScore).
  - `neural_mix/composite.py` (NeuralMixScorer).
- `components/bpm.py` и `components/energy.py` — становятся re-exports из `scoring/components/`.
- `bulk_scorer.py` → distribution of functions to per-component files; модуль остаётся как backward-compat shim (re-exports `score_*_bulk` functions + `hard_reject_mask_bulk`).

**Tests**:
- `tests/domain/transition/scoring/test_*.py` per-component (scalar + bulk in one file).
- Parity tests расширены: каждый component's scalar vs bulk внутри одного теста.
- Существующие `test_bulk_scorer_parity.py` и `test_neural_mix.py` продолжают проходить (re-export shims).
- Golden tests из PR 0 — все зелёные.

**Acceptance**: после PR 3 — основная decomposition done. `scorer.py` пока ещё legacy, но компоненты разнесены.

### PR 4 — TransitionEvaluator + scorer adapter

**Branch**: `refactor/transition-arch-v4-evaluator`

**Цель**: новый orchestrator `TransitionEvaluator`. Legacy `TransitionScorer` становится тонким adapter'ом.

**Файлы созданы**:
- `app/domain/transition/orchestrator.py` — `TransitionEvaluator` class + legacy `TransitionScorer` adapter (described in 4.5).

**Файлы изменены**:
- `app/domain/transition/scorer.py` — теперь re-exports `TransitionScorer` из `orchestrator.py`.
- Internal helpers `_apply_section_overlay`, `_compute_score` — **удалены** (заменены `DEFAULT_OVERLAY_CHAIN` + `CompositeScorer`).

**Tests**:
- `tests/domain/transition/test_orchestrator.py` — direct test of `TransitionEvaluator.evaluate*`.
- Существующий `test_scorer.py` продолжает проходить (через adapter).
- Все golden tests зелёные (это критическая контрольная точка для "no behaviour change").

**Acceptance**: можно поменять `TransitionScorer` в `app/server/lifespan.py` на `TransitionEvaluator` и всё работает (этот switch — в PR 7).

### PR 5 — Recipe layer (Template Method builders)

**Branch**: `refactor/transition-arch-v5-recipe`

**Цель**: распределить `builders.py` (374 LOC) + `recipe.py` (333 LOC).

**Файлы созданы**:
- `recipe/model.py` — `NeuralMixRecipe` + `StemKeyframe` + `MuteFXEvent` dataclasses (no logic).
- `recipe/constants.py` — `LEVEL_SILENT`, `LEVEL_UNITY`, `DEFAULT_TRANSITION_BARS`, `MuteFXTrigger`, `Deck`.
- `recipe/serialization.py` — `to_json/from_json` (extracted from `recipe.py`).
- `recipe/envelopes/{linear_fade,hold_then_fade,kill_with_echo,enter_ramp}.py` — переиспользуемые helpers (бывшие `_hold`, `_ramp`, `_crossfade_full`).
- `recipe/builders/base.py` — `BaseRecipeBuilder` (Template Method).
- `recipe/builders/{fade,echo_out,vocal_sustain,harmonic_sustain,drum_swap,vocal_cut,drum_cut}.py` — 7 concrete builders.
- `recipe/factory.py` — `build_recipe` + `DEFAULT_BUILDERS`.
- `recipe/orchestrator.py` — `build_recipe_for_pair` (extracted from `picker.py`).

**Файлы изменены**:
- `recipe.py` → re-exports.
- `builders.py` → re-exports.

**Tests**:
- `tests/domain/transition/recipe/test_*.py` per-builder.
- Существующие `test_recipe.py` и `test_builders.py` проходят через re-exports.
- Golden recipe tests из PR 0 — все зелёные (per-keyframe match).

### PR 6 — Picker (CoR + proxies)

**Branch**: `refactor/transition-arch-v6-picker`

**Цель**: разнести `picker.py` (313 LOC) на pipeline + 3 proxies + 7 rules.

**Файлы созданы**:
- `picker/api.py` — `PickerDecision` dataclass + `PickerRule` Protocol.
- `picker/pipeline.py` — `PickerPipeline.pick(...)` + functional `pick_neural_mix(...)` adapter.
- `picker/proxies/vocal_activity.py` — `SpectralVocalActivityDetector`.
- `picker/proxies/harmonic_motif.py` — `HarmonicMotifDetector`.
- `picker/proxies/camelot_compatibility.py` — `CamelotCompatibilityCheck`.
- `picker/rules/{hard_reject_rescue,drum_only_section,vocal_active,harmonic_sustain,energy_drop_to_slam,ambient_or_cooldown,default_echo_out}.py` — 7 rules.

**Файлы изменены**:
- `picker.py` → re-exports `PickerDecision`, `pick_neural_mix`, `build_recipe_for_pair` (последний теперь из `recipe/orchestrator.py`).

**Tests**:
- `tests/domain/transition/picker/test_*.py` per-rule + per-proxy.
- Существующий `test_picker.py` проходит через re-exports.
- Golden picker decisions из PR 0 — все зелёные.

### PR 7 — Cleanup + DI switch + docs

**Branch**: `refactor/transition-arch-v7-cleanup`

**Цель**: финальные cleanup'ы, удаление dead-shims, обновление документации, release v1.5.0.

**Файлы изменены**:
- `app/server/lifespan.py` — `TransitionScorer` → `TransitionEvaluator` в DI (через `TransitionScorerProtocol`).
- `app/handlers/transition_persist.py` — `TransitionScorerProtocol` обновляется (если нужны новые methods).
- `app/domain/transition/__init__.py` — финализация frozen public API + новые optional exports.
- Удаление dead code: `scorer.py:_apply_section_overlay`, `_compute_score`, `_ALL_INTENTS` (мигрируют в `orchestrator.py` или удаляются).
- Удаление `INTENT_WEIGHT_MODIFIERS` дубликата из `weights.py`.
- `docs/transition-scoring.md` — обновить разделы:
  - "Module Layout" — новая структура.
  - "Extension Points" (NEW) — как добавить component / rule / builder / overlay.
- `docs/transition-architecture.md` (NEW) — диаграмма зависимостей + GoF patterns mapping.
- `CHANGELOG.md` — entry `## [1.5.0] - 2026-MM-DD` — `### Changed (internal)`: список архитектурных изменений с акцентом на "no behaviour change".
- Версии в 4 файлах: `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CLAUDE.md`.

**Acceptance test**:
- `tests/domain/transition/test_extension_*.py` — все 4 acceptance тестов зелёные (OCP demonstration).

**Acceptance**:
- `make check` зелёный.
- Все golden tests зелёные.
- Все acceptance tests зелёные.
- Tag `v1.5.0` создан и pushed.
- GitHub Release v1.5.0 published.

---

## 8. Testing Strategy

### 8.1 Three-level golden tests (frozen behavior guard)

**Level 1: Scoring math snapshots** (`test_golden_scoring.py`)

```python
# tests/domain/transition/_golden/scoring.json
[
    {
        "case_id": "phase_0_acid_pair_173_177",
        "from_track": {"bpm": 124.5, "key_code": 8, "integrated_lufs": -8.2,
                       "pitch_salience_mean": 0.78, "spectral_centroid_hz": 3400.0,
                       "energy_bands": [0.1, 0.15, 0.12, 0.18, 0.22, 0.23], ...},
        "to_track":   {"bpm": 125.1, "key_code": 8, "integrated_lufs": -7.9, ...},
        "section_context": null,
        "intent": null,
        "expected": {
            "bpm": 0.99..., "energy": 0.96..., "drums": 0.84...,
            "bass": 0.92..., "harmonics": 0.81..., "vocals": 0.42...,
            "overall": 0.83..., "hard_reject": false,
            "best_transition": "echo_out", "section_pair_class": null
        }
    },
    {
        "case_id": "phase_1_drum_only_overlay",
        "from_track": {...}, "to_track": {...},
        "section_context": {"from_section": "OUTRO", "to_section": "INTRO"},
        "intent": null,
        "expected": {..., "section_pair_class": "drum_only"}
    },
    // ... 18 more representative cases
]
```

Tolerance 1e-9. Если число чуть-чуть изменилось — это либо bug либо conscious change, который должен быть в CHANGELOG с пояснением.

**Level 2: Recipe envelope snapshots** (`test_golden_recipes.py`)

```python
# tests/domain/transition/_golden/recipes_fade_32.json
{
    "transition": "fade", "bars": 32,
    "keyframes": [
        {"bar": 0.0, "deck": "A", "stem": "drums", "level_db": 0.0},
        {"bar": 32.0, "deck": "A", "stem": "drums", "level_db": -120.0},
        // ... per-keyframe
    ],
    "fx_events": []
}
```

Каждый из 7 presets × bars ∈ {16, 32, 64} = 21 файлов.

**Level 3: Picker decision snapshots** (`test_golden_picker.py`)

30 representative scenarios → expected `PickerDecision` (transition, confidence, reason).

**Level 4: Bulk parity** (`test_bulk_scorer_parity.py` — расширение существующего)

Расширить existing: добавить scenarios с DRUM_ONLY context (сейчас не покрыт), и проверить `score_pairs_bulk` против `evaluator.evaluate_pairs`.

### 8.2 Per-PR unit tests

Каждый migrating PR добавляет per-file unit tests в зеркальной структуре:
- `tests/domain/transition/scoring/components/test_drums.py` — direct test of `DrumsComponent.score` and `DrumsComponent.score_pairs`.
- `tests/domain/transition/picker/rules/test_drum_only_section.py` — direct test of the rule.
- ... и т.д.

### 8.3 Architecture tests (`import-linter`)

Добавить новый contract в `.importlinter`:

```toml
[importlinter:contract:transition-layers]
name = Transition subsystem layers
type = layers
layers =
    app.domain.transition.orchestrator
    app.domain.transition.scoring
    app.domain.transition.constraints
    app.domain.transition.picker
    app.domain.transition.recipe
    app.domain.transition.neural_mix
    app.domain.transition.context
    app.domain.transition.kernels
    app.domain.transition.api
    app.domain.transition.enums

containers = app.domain.transition
ignore_imports =
    # api.py needs all enums for Protocol signatures
    app.domain.transition.api -> app.domain.transition.enums
```

### 8.4 Mypy strict + ruff

Все Protocol'ы помечены `@runtime_checkable`. Strict mypy проверяет что concrete classes имплементируют Protocol surface (через `assert_type` патрерны в unit tests).

---

## 9. Risks + Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Golden tests слишком strict → false positives на float-noise при miграции одной формулы из scalar в bulk | Medium | Tolerance 1e-9 для component values; 1e-7 для overall (где накапливается ошибка); snapshot regeneration tool `scripts/regen_transition_golden.py` с явным review требованием. |
| `bulk_scorer.py` decomposition теряет ~10-30% perf на GA hot path из-за per-component dispatch overhead | High (perf-critical) | `CompositeScorer.score_pairs` инлайнит chain через тип-проверку: если все components поддерживают bulk → одна batch call; иначе fallback. Benchmark в PR 3: ≤ 5% perf regression на 200-track pool — acceptable; > 5% — investigate. |
| Public API drift из-за миграции внутренностей | High (breaking change) | Frozen `__all__` list checked by `tests/domain/transition/test_public_api_freeze.py` — assert `set(__all__) == FROZEN_SET`. Любой `__all__` edit требует explicit test edit. |
| 6 PR'ов растягиваются на месяц, отвлекают от Phase 2 calibration | Low | Acceptance criteria per-PR — каждый stands alone. Можно паузить после любого PR'а без блокировки прода. |
| Protocol overhead (runtime_checkable instance checks) замедляет hot path | Low | Protocol'ы только в DI / тестах, в горячем пути компоненты типизированы конкретно. Runtime instance check только в `assert isinstance(...)` гейтах. |
| Конфликты с активной работой над transition-scoring (Phase 2 в ROADMAP) | Medium | Координировать с пользователем перед PR 3 — если Phase 2 calibration уже в работе, отложить PR 3 до её мерджа. |
| GoF over-engineering: 55 файлов по 50 LOC vs 16 файлов по 200 LOC — IDE navigation harder | Low | Каноничный layout уже принят в проекте (`app/audio/analyzers/` имеет 18 файлов). Существующая convention. Mitigation: explicit `__init__.py` экспорты + `docs/transition-architecture.md` с map. |
| Lazy import в `transition_persist.py` (нужен для import-linter contract `v2-server-no-domain`) — protocol changes break it | Medium | `TransitionScorerProtocol` definition остаётся в handler module. Protocol body не меняется в этом рефакторинге (signature совместима). |
| Recipe JSON shape change | High (breaking, DB persisted) | `NeuralMixRecipe.to_dict()` / `to_json()` / `from_json()` — golden tests за recipe roundtrip обязательны. JSON schema не меняется. |
| Phase 1 (v2 section_pair_class) был только что мерджнут (PR #219, ~5h до этой spec) → возможны нестабильности | Medium | Дополнительный smoke test в PR 0: репродукция Phase 0 + Phase 1 case 173→177 из v1.4.0 CHANGELOG verification. |

---

## 10. Acceptance Criteria (DoD)

После PR 7:

- [ ] `app/domain/transition/orchestrator.py:TransitionEvaluator` существует и реализует `TransitionEvaluatorProtocol`.
- [ ] `app/domain/transition/orchestrator.py:TransitionScorer` — тонкий adapter, ≤ 60 LOC.
- [ ] `app/domain/transition/scoring/components/` содержит 6 файлов, каждый имплементирует `ScoringComponent` со scalar + bulk методами.
- [ ] `app/domain/transition/picker/rules/` содержит 7 файлов, каждый имплементирует `PickerRule`.
- [ ] `app/domain/transition/recipe/builders/` содержит 7 файлов + `base.py`, каждый имплементирует `RecipeBuilder` или наследует `BaseRecipeBuilder`.
- [ ] `app/domain/transition/constraints/specs/` содержит 3 файла.
- [ ] `app/domain/transition/scoring/overlays/` содержит 3 файла.
- [ ] `app/domain/transition/picker/proxies/` содержит 3 файла.
- [ ] Public API (`__all__` в `app/domain/transition/__init__.py`) содержит точно те же 21 имя + опционально новые protocols/registries.
- [ ] Mypy strict + ruff clean + import-linter happy + `make check` зелёный.
- [ ] Все golden tests зелёные (Level 1, 2, 3, 4).
- [ ] Все acceptance tests (`test_extension_*.py`) зелёные.
- [ ] Coverage не упал (baseline = `pytest --cov` до PR 0).
- [ ] `bulk_scorer.py` существует только как backward-compat re-export shim (≤ 30 LOC).
- [ ] `neural_mix.py` существует только как backward-compat re-export shim (≤ 30 LOC).
- [ ] `picker.py` существует только как backward-compat re-export shim (≤ 30 LOC).
- [ ] `builders.py` существует только как backward-compat re-export shim (≤ 30 LOC).
- [ ] `recipe.py` существует только как backward-compat re-export shim (≤ 30 LOC).
- [ ] CHANGELOG v1.5.0 описывает изменения как "internal refactor, no behaviour change".
- [ ] [docs/transition-scoring.md](../../transition-scoring.md) обновлён: новый "Module Layout" + раздел "Extension Points".
- [ ] [docs/transition-architecture.md](../../transition-architecture.md) создан: диаграмма зависимостей + GoF patterns.
- [ ] PR'ы #0-#7 squash-merged. Tag `v1.5.0` создан и pushed. GitHub Release published.

---

## 11. Open Questions

Все resolved автономно в Section 3 (Decisions Matrix). Дальнейшие architectural questions для будущих фаз:

1. **Phase 2 — per-subgenre `ComponentWeightProfile` Strategy.** Architecture готова через `WeightOverlay`; нужен новый `SubgenreOverlay` strategy + конфигурируемые profiles. Out of scope v1.5.0.
2. **Phase 3 — stem separation integration.** `VocalActivityDetector` Protocol готов; нужен `StemVocalActivityDetector` impl поверх `StemSeparator` analyzer (когда последний реализуется). Out of scope v1.5.0.
3. **Phase 4 — new presets (FILTER_SWEEP, LOOP_ROLL, STUTTER_FX, HARD_CUT).** Architecture готова через `RecipeBuilder` + `PickerRule`. Out of scope v1.5.0.

---

## Appendix A: Public API Freeze List

Эти 21 имя MUST keep working after every PR в этом рефакторинге:

```text
DEFAULT_TRANSITION_BARS
LEVEL_SILENT
LEVEL_UNITY
MuteFXEvent
MuteFXTrigger
NeuralMixRecipe
NeuralMixScore
NeuralMixScorer
NeuralMixStem
NeuralMixTransition
PickerDecision
SectionContext
StemKeyframe
TransitionScore
TransitionScorer
bpm_distance
build_recipe
build_recipe_for_pair
correlation
cosine_similarity
pick_neural_mix
```

Total: **21 names**. Любое расширение `__all__` — additive (новые `ScoringComponent`, `PickerRule`, `RecipeBuilder` Protocol и `TransitionEvaluator` class); удаление какого-либо имени из списка выше — breaking change, не допускается в v1.5.x.

## Appendix B: Glossary

- **Strategy** — interface (Python Protocol) + множество implementations, выбираемых runtime / DI.
- **Composite** — объект, агрегирующий list[Strategy] и применяющий их к input в едином потоке.
- **Chain of Responsibility (CoR)** — series of Strategy'ев, итерируемая first-match-wins.
- **Template Method** — base class с алгоритмом, частично abstract; concrete subclass переопределяет hook methods.
- **Factory Method / Registry** — функция/коллекция, возвращающая Strategy instance по ключу (enum / type / name).
- **Protocol** (Python typing) — структурный тип-интерфейс. С `@runtime_checkable` поддерживает `isinstance(obj, MyProtocol)`.
- **Adapter** — class/функция, преобразующая старый API в новый или наоборот. Здесь используется для backward-compat (`TransitionScorer` адаптирует к `TransitionEvaluator`).
- **Golden test** — snapshot expected output текущего поведения; защищает от regression при рефакторинге.
- **Parity test** — сравнение двух parallel implementations того же алгоритма (scalar vs bulk).
- **Overlay (в нашем контексте)** — `WeightOverlay` Strategy, трансформирующая base weights dict в context-aware weights.
- **Hook** (в Template Method) — method, который subclass переопределяет; не должен вызываться напрямую клиентом.
- **Co-located** — две реализации одного концепта в одном файле (scalar + bulk per scoring component).
