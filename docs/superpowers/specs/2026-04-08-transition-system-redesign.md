# Transition System Redesign

> Дата: 2026-04-08
> Branch: `feat/player-transition-system`
> Research: [docs/research/2026-04-08-techno-transitions-research.md](../../research/2026-04-08-techno-transitions-research.md)
> Связано: `app/domain/transition/scorer.py` (538 строк), `app/services/transition.py`, `app/services/set/scoring.py`, `app/domain/optimization/{genetic,greedy,fitness}.py`, `app/core/transition_intent.py`

---

## Summary

Текущий `TransitionScorer` — это монолит из 538 строк с захардкоженными константами, шестью компонентами в одном файле, отсутствующей моделью phrasing/structure и расхождением `docs/transition-scoring.md` с реальным кодом. Research (см. отдельный документ) показывает три фундаментальных дефекта:

1. **Phrasing/structure не моделируется** — поля `mix_in_point_ms`, `mix_out_point_ms`, `from_section_id`, `to_section_id` существуют в БД, но всегда `NULL`. В академической литературе structural alignment — самый сильный фактор для percussion-driven жанров (Vande Veire 2018, Zehren 2022).
2. **Веса перекошены** относительно того, что реально важно по статистике живых сетов (Kim ISMIR 2020): MFCC similarity #1, loudness alignment #2, key — слабее чем думает индустрия.
3. **Магические числа всюду** — нельзя ни тестировать, ни тюнить.

Редизайн решает эти три проблемы **без смены публичного API** (`TransitionScorer().score(a, b, intent=…)` и `recommend_style(score)` остаются стабильными — на них завязаны GA, greedy, services, MCP tools и panel waveform player).

Это **не переписывание с нуля** — это структурный рефакторинг + одна новая фича (section-awareness) + калибровка весов.

---

## Goals

1. Декомпозировать монолит scorer.py 538 строк → пакет из 8-10 маленьких модулей с одной ответственностью.
2. Вынести **все** магические числа в `app/domain/transition/weights.py` (один источник правды).
3. Внедрить **section-aware scoring**: harmonic вес схлопывается до ~0 для outro→intro pair (drum-only), и наоборот растёт для full-track→full-track pair.
4. Внедрить **mix-point detection service**: заполнять `mix_in_point_ms`/`mix_out_point_ms` на основе beatgrid + sections + 16-bar grid.
5. Перебалансировать `DEFAULT_TRANSITION_WEIGHTS` на базе таблицы из research §4.4.
6. Параметризовать `recommend_style` thresholds (через dataclass `StyleRules`).
7. Улучшить `infer_intent` v2 — учитывать SetTemplate phase position, а не только глобальный 0.2/0.85 cutoff.
8. Синхронизировать `docs/transition-scoring.md` с реальным кодом.
9. Сохранить совместимость: все 5 callers (services, optimization, MCP tools, panel) продолжают работать без изменений сигнатур.

## Non-Goals

- НЕ добавляю новые поля в БД. Использую существующие nullable поля (`mix_in_point_ms`, `from_section_id`).
- НЕ переписываю GA / greedy / fitness — только подключаю к новому фасаду.
- НЕ трогаю panel/waveform player — контракт `recommended_style` + `recommended_bars` сохраняется байт-в-байт.
- НЕ добавляю stem separation, GAN, ML модели. Гибрид rule-based — это валидированный SOTA (Chen 2022 показал что end-to-end ML провалился).
- НЕ пытаюсь построить sound сегментатор для техно (Foote/MSAF плохо работают). Использую existing `track_sections` + downbeat grid.
- НЕ меняю Camelot wheel или harmonic distance таблицу — только добавляю section-relax.
- НЕ перекладываю transition_intent.py из core в domain «потому что чище» — это slippery slope расширения скоупа.

---

## Architecture

### Текущая структура

```text
app/domain/transition/
├── __init__.py            (re-exports)
├── math_helpers.py         (cosine, correlation, bpm_distance)
└── scorer.py               (538 строк, всё)

app/core/
├── transition_intent.py    (TransitionIntent enum + INTENT_WEIGHT_MODIFIERS + infer_intent)
└── constants.py            (DEFAULT_TRANSITION_WEIGHTS, TransitionStyle, TRANSITION_STYLE_PROFILES)

app/config.py
└── Settings.transition_hard_reject_*, scoring_*  (some thresholds, but not all)
```

### Целевая структура

```bash
app/domain/transition/
├── __init__.py             (public API: TransitionScorer, TransitionScore,
│                            recommend_style, style_profile, TransitionIntent)
├── math_helpers.py         (unchanged)
├── weights.py              (NEW: ALL magic numbers — sigmas, thresholds, normalizers)
├── score.py                (NEW: TransitionScore dataclass — moved out of scorer.py)
├── hard_constraints.py     (NEW: _check_hard_constraints, returns Rejection|None)
├── components/
│   ├── __init__.py
│   ├── bpm.py              (NEW: score_bpm function)
│   ├── harmonic.py         (NEW: score_harmonic function with section-aware relax)
│   ├── energy.py           (NEW: score_energy function)
│   ├── spectral.py         (NEW: score_spectral function)
│   ├── groove.py           (NEW: score_groove function)
│   └── timbral.py          (NEW: score_timbral function)
├── section_context.py      (NEW: dataclass SectionContext, helper to determine
│                            "are we in a mixable region pair?")
├── style.py                (NEW: recommend_style + style_profile + StyleRules dataclass)
├── intent.py               (NEW: re-exports from app.core.transition_intent for
│                            domain locality; do NOT delete the original)
└── scorer.py               (~80 строк, only orchestration:
                              hard_check → component dispatch → weighted sum)

app/services/
└── mix_point_service.py    (NEW: detects + persists mix_in_point_ms/mix_out_point_ms
                              for all set items based on beatgrid + sections)
```

### Public API (frozen)

These imports MUST keep working without changes:

```python
from app.domain.transition import (
    TransitionScorer,
    TransitionScore,
    recommend_style,
    style_profile,
)
from app.services.transition import TransitionScorer, TrackFeatures  # re-exports
```

Method signatures (frozen):

```python
TransitionScorer(weights: dict[str, float] | None = None)

scorer.score(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    intent: TransitionIntent | None = None,
) -> TransitionScore

scorer.score_with_candidates(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    candidate_bpm_distance: float | None = None,
    candidate_key_distance: int | None = None,
    candidate_energy_delta: float | None = None,
) -> TransitionScore

recommend_style(score: TransitionScore) -> TransitionStyle  # pure function
style_profile(style: TransitionStyle) -> dict[str, float | str]
```

**New optional API** (additive, backward-compatible):

```python
scorer.score(
    from_t, to_t,
    *,
    intent=None,
    section_context: SectionContext | None = None,  # NEW
) -> TransitionScore

# Where SectionContext is:
@dataclass(frozen=True)
class SectionContext:
    """Section types for the mix-out (from_t) and mix-in (to_t) windows.

    Used for harmonic-relaxation and weight rebalancing when the actual
    mix happens on percussion-only intro/outro regions.
    """
    from_section: SectionType | None  # what section we're mixing OUT of
    to_section: SectionType | None    # what section we're mixing INTO

    @property
    def is_drum_only_pair(self) -> bool:
        """Both sides are intro/outro/sustain — harmonic mostly irrelevant."""
        drum_only = {SectionType.INTRO, SectionType.OUTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
        return self.from_section in drum_only and self.to_section in drum_only
```

When `section_context` is `None`, behavior is identical to today (backward compat).

---

## Components — what each file does

### `weights.py` — single source of truth for tuning

```python
"""All transition scoring magic numbers in one place.

Pure data — no I/O, no logic. Imported by component scorers and `recommend_style`.
Values are derived from research/2026-04-08-techno-transitions-research.md §4.4.
"""

from dataclasses import dataclass, field

# ── Component weights (sum = 1.0) ────────────────────────
# Rebalanced from research §4.4: MFCC #1 (Kim 2020), key overrated (Bibbó 2022),
# structural alignment crucial for percussion-driven (Vande Veire 2018).
DEFAULT_WEIGHTS: dict[str, float] = {
    "bpm":      0.20,
    "harmonic": 0.12,  # was 0.20 — Kim 2020 finding
    "energy":   0.18,  # was 0.23
    "spectral": 0.20,  # was 0.15 — MFCC is #1 in real mixes
    "groove":   0.15,  # was 0.10 — percussion-driven matters
    "timbral":  0.15,  # was 0.10
}
# Total = 1.00

# ── BPM scoring ──────────────────────────────────────────
BPM_GAUSS_SIGMA: float = 3.0           # ~2.5% on 124 BPM — Ishizaki finding
BPM_STABILITY_FLOOR: float = 0.7       # max 30% penalty for unstable tempo

# ── Harmonic scoring ─────────────────────────────────────
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
ATONAL_RELAX_FLOOR: float = 0.8         # both atonal → at least 0.8
HNR_NORM_RANGE: tuple[float, float] = (-30.0, 0.0)  # dB → 0.5..1.0
HNR_NORM_FLOOR: float = 0.5
TONNETZ_BLEND: float = 0.30             # weight of tonnetz cosine vs Camelot base
KEY_CONFIDENCE_BLEND_THRESHOLD: float = 0.5
DRUM_ONLY_HARMONIC_RELAX: float = 0.85  # NEW: drum-only pair → max(score, 0.85)

# ── Energy scoring ───────────────────────────────────────
ENERGY_SIGMOID_DIVISOR: float = 1.5     # was 3.0 — Kim 2020: DJs hold step <1 dB
LRA_DIFF_PENALTY_THRESHOLD: float = 5.0
LRA_DIFF_PENALTY: float = 0.10
CREST_DIFF_PENALTY_THRESHOLD: float = 4.0
CREST_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Spectral scoring ─────────────────────────────────────
SPECTRAL_SUB_WEIGHTS: dict[str, float] = {
    "mfcc":         0.30,
    "centroid":     0.20,
    "energy_bands": 0.20,
    "rolloff":      0.15,
    "slope":        0.10,
    "flux":         0.05,
}
DISSONANCE_PAIR_THRESHOLD: float = 0.4
DISSONANCE_PENALTY: float = 0.15
COMPLEXITY_DIFF_THRESHOLD: float = 10.0
COMPLEXITY_PENALTY: float = 0.10

# ── Groove scoring ───────────────────────────────────────
GROOVE_SUB_WEIGHTS: dict[str, float] = {
    "onset_rate":     0.25,
    "kick_prominence":0.25,
    "beat_loudness":  0.20,
    "pulse_clarity":  0.10,
    "hp_ratio":       0.10,
    "tempogram":      0.10,
}

# ── Timbral scoring ──────────────────────────────────────
TIMBRAL_SPECTRAL_CONTRAST_NORM: float = 15.0  # dB
TIMBRAL_PITCH_SALIENCE_NORM: float = 0.5
TIMBRAL_DANCEABILITY_NORM: float = 3.0
TIMBRAL_DYNAMIC_COMPLEXITY_NORM: float = 10.0
TIMBRAL_SUB_WEIGHTS: dict[str, float] = {
    "spectral_contrast": 0.35,
    "pitch_salience":    0.35,
    "danceability":      0.15,
    "dynamic_complexity":0.15,
}

# ── Style recommendation thresholds ──────────────────────
@dataclass(frozen=True)
class StyleRules:
    """Decision tree thresholds for `recommend_style`.

    Defaults reflect current behavior; can be overridden per-template
    in the future.
    """
    spectral_collision_cutoff: float = 0.45
    energy_gap_cutoff: float = 0.40
    harmonic_drift_cutoff: float = 0.55
    perfect_bpm_cutoff: float = 0.95
    perfect_harmonic_cutoff: float = 0.85
    perfect_groove_cutoff: float = 0.75
    confident_overall_cutoff: float = 0.75

DEFAULT_STYLE_RULES = StyleRules()

# ── Section-aware modifiers ──────────────────────────────
# When the mix happens on intro/outro percussion-only windows,
# suppress harmonic weight and boost groove (Vande Veire 2018).
DRUM_ONLY_WEIGHT_OVERRIDE: dict[str, float] = {
    "bpm":      0.22,
    "harmonic": 0.05,  # collapsed
    "energy":   0.18,
    "spectral": 0.20,
    "groove":   0.20,  # boosted
    "timbral":  0.15,
}
```

### `score.py` — TransitionScore dataclass (moved out of scorer.py)

Pure dataclass, no logic. Single import target for `recommend_style` callers. Same shape as today.

### `hard_constraints.py` — early-exit gate

```python
def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> TransitionScore | None:
    """Return zero-score TransitionScore on rejection, or None if all pass."""
```

Same logic as current `_check_hard_constraints` in scorer.py:103, just moved to its own module + made standalone function (no `self`).

### `components/{bpm,harmonic,energy,spectral,groove,timbral}.py`

Each file exports one pure function `score_X(from_t, to_t, *, weights=DEFAULT_*) -> float` (and optionally `section_context` for harmonic). Same logic as current `_score_X` methods, but:

1. Standalone (no `self`).
2. All numeric constants come from `weights.py`, none hardcoded.
3. Each file has its own focused unit tests.

`harmonic.py` adds the section-aware relaxation:

```python
def score_harmonic(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
) -> float:
    score = _compute_harmonic(from_t, to_t)  # current logic verbatim

    # Section-aware relaxation: drum-only mix region → harmonic mostly irrelevant
    if section_context is not None and section_context.is_drum_only_pair:
        return max(score, DRUM_ONLY_HARMONIC_RELAX)

    return score
```

### `section_context.py` — `SectionContext` dataclass (shown above)

### `style.py` — recommend_style + StyleRules

Same logic as current `recommend_style` in scorer.py:484, but reads thresholds from `StyleRules` instead of inline literals. Default rules in `DEFAULT_STYLE_RULES`. Function signature unchanged: `recommend_style(score) -> TransitionStyle`.

### `scorer.py` (new, ~80 lines)

```python
class TransitionScorer:
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        rules: StyleRules = DEFAULT_STYLE_RULES,
    ) -> None:
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        self.rules = rules

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        # Pick weight set: drum-only override > intent override > default
        if section_context is not None and section_context.is_drum_only_pair:
            w = DRUM_ONLY_WEIGHT_OVERRIDE
        elif intent is not None:
            w = INTENT_WEIGHT_MODIFIERS[intent]
        else:
            w = self.weights

        bpm = score_bpm(from_t, to_t)
        harmonic = score_harmonic(from_t, to_t, section_context=section_context)
        energy = score_energy(from_t, to_t)
        spectral = score_spectral(from_t, to_t)
        groove = score_groove(from_t, to_t)
        timbral = score_timbral(from_t, to_t)

        overall = (
            w["bpm"] * bpm + w["harmonic"] * harmonic + w["energy"] * energy
            + w["spectral"] * spectral + w["groove"] * groove + w["timbral"] * timbral
        )

        return TransitionScore(
            bpm=bpm, harmonic=harmonic, energy=energy,
            spectral=spectral, groove=groove, timbral=timbral, overall=overall,
        )
```

### `mix_point_service.py` — NEW service

```python
class MixPointService:
    """Detect mix-in/mix-out points for set items based on beatgrid + sections.

    Algorithm (Zehren 2022 + Vande Veire 2018):
    1. Get the track's beatgrid (downbeats list).
    2. Get the track's structural sections.
    3. Mix-out point = first downbeat in the OUTRO/SUSTAIN/AMBIENT section,
       quantized to nearest 16-bar phrase boundary.
       Fallback: 32 bars before track end, quantized to nearest downbeat.
    4. Mix-in point = first downbeat in the INTRO/AMBIENT section,
       quantized to nearest 16-bar phrase boundary.
       Fallback: track start (0 ms).
    """

    def __init__(
        self,
        beatgrid_repo: BeatgridRepository,
        section_repo: TrackSectionRepository,
    ) -> None: ...

    async def detect_mix_points(
        self, track_id: int
    ) -> tuple[int | None, int | None]:
        """Return (mix_in_ms, mix_out_ms). None if no beatgrid available."""
        ...

    async def populate_set_mix_points(self, set_id: int, version_id: int) -> int:
        """Compute and persist mix points for all items in a set version.

        Updates SetItem.mix_in_point_ms / mix_out_point_ms.
        Also fills SetItem.from_section_id / to_section_id by looking up
        which section contains each mix point.

        Returns count of items updated.
        """
        ...
```

This service is **invoked by `deliver_set` only**. Build/rebuild does NOT call it (avoid slowing down GA). Instead, `score_pair` and `score_transitions` accept an optional pre-computed `SectionContext` from the caller.

### `intent.py` v2 — phase-aware

Current `infer_intent`:

```python
def infer_intent(set_position, energy_delta_lufs):
    if set_position < 0.2: return RAMP_UP
    if set_position > 0.85: return COOL_DOWN
    if energy_delta_lufs > 2.0: return RAMP_UP
    if energy_delta_lufs < -2.0: return COOL_DOWN
    return MAINTAIN
```

v2 (still in `app/core/transition_intent.py`, NOT moved):

```python
def infer_intent(
    set_position: float,
    energy_delta_lufs: float,
    template: SetTemplate | None = None,
) -> TransitionIntent:
    """Phase-aware intent.

    When `template` is provided, position thresholds shift to match
    the template's energy arc (warm_up_30 vs peak_hour_60 etc.).
    """
    # Per-template phase thresholds (warmup_end, peak_start, peak_end)
    phase_table = {
        SetTemplate.WARM_UP_30:    (0.50, 0.70, 0.85),
        SetTemplate.CLASSIC_60:    (0.20, 0.50, 0.80),
        SetTemplate.PEAK_HOUR_60:  (0.10, 0.30, 0.90),
        SetTemplate.ROLLER_90:     (0.15, 0.40, 0.85),
        SetTemplate.PROGRESSIVE_120:(0.30, 0.60, 0.85),
        SetTemplate.WAVE_120:      (0.20, 0.50, 0.80),
        SetTemplate.CLOSING_60:    (0.05, 0.15, 0.50),
        SetTemplate.FULL_LIBRARY:  (0.20, 0.50, 0.85),
    }
    warmup_end, _peak_start, peak_end = phase_table.get(
        template, (0.20, 0.50, 0.85)
    )

    if set_position < warmup_end:
        return TransitionIntent.RAMP_UP
    if set_position > peak_end:
        return TransitionIntent.COOL_DOWN
    if energy_delta_lufs > 2.0:
        return TransitionIntent.RAMP_UP
    if energy_delta_lufs < -2.0:
        return TransitionIntent.COOL_DOWN
    return TransitionIntent.MAINTAIN
```

Backward compat: when `template=None`, behavior is identical to today.

---

## Data Flow

```text
score_pair (existing tool)
  ↓
TransitionScorer.score(from_t, to_t)
  ↓
hard_constraints.check_hard_constraints  ── reject? → zero-score
  ↓
components.{bpm,harmonic,energy,spectral,groove,timbral}.score_*  ── parallel-safe pure functions
  ↓
weighted_sum(components, weights)
  ↓
TransitionScore
  ↓
recommend_style(score) → TransitionStyle (used by panel waveform player)

deliver_set (new path)
  ↓
MixPointService.populate_set_mix_points(set_id, version_id)
  ↓
For each consecutive pair:
  - SetItem.mix_out_point_ms (from_t)
  - SetItem.mix_in_point_ms (to_t)
  - SetItem.from_section_id, to_section_id
  ↓
score_transitions(set_id) — re-score with section_context
  ↓
TransitionScorer.score(..., section_context=SectionContext(from_sec, to_sec))
  ↓
Drum-only pairs get DRUM_ONLY_WEIGHT_OVERRIDE → harmonic suppressed
  ↓
TransitionScore (now structurally aware)
  ↓
Persisted to `transitions` table
```

---

## Migration Plan (TDD, no big bang)

The redesign happens in **6 small commits**, each independently `make check`-clean:

### Commit 1 — Extract weights.py
- Create `app/domain/transition/weights.py` with all constants (none yet referenced).
- Tests: `tests/test_domain/test_transition_weights.py` — sanity (sum=1.0, types).
- No functional change.

### Commit 2 — Extract score.py + hard_constraints.py
- Move `TransitionScore` dataclass to `score.py`.
- Move `_check_hard_constraints` to `hard_constraints.py:check_hard_constraints` (standalone function).
- `scorer.py` imports them. All existing tests must pass.

### Commit 3 — Extract components/
- One file per `_score_X` method → standalone function.
- Each file uses `weights.py` constants instead of literals.
- `scorer.py` becomes a thin orchestrator.
- Existing tests in `test_transition_scoring_*.py` must pass with no edits (public API unchanged).

### Commit 4 — Extract style.py + StyleRules
- Move `recommend_style` and `style_profile` to `style.py`.
- Introduce `StyleRules` dataclass; default = current behavior.
- Tests in `test_transition_style.py` must pass.

### Commit 5 — Section-aware scoring
- New `section_context.py` with `SectionContext` dataclass.
- `score_harmonic` accepts optional `section_context`, applies `DRUM_ONLY_HARMONIC_RELAX`.
- `TransitionScorer.score` accepts optional `section_context`, uses `DRUM_ONLY_WEIGHT_OVERRIDE` when applicable.
- New tests: drum-only pair gets harmonic ≥ 0.85, weights override applied.

### Commit 6 — MixPointService + intent v2
- New `app/services/mix_point_service.py`.
- Tests with seeded beatgrid + sections fixtures.
- `infer_intent` v2 in `app/core/transition_intent.py` accepts optional `template`.
- `set/scoring.py` and `deliver_set` invoke `MixPointService` and pass `SectionContext` to scorer.
- Update `DEFAULT_TRANSITION_WEIGHTS` in `app/core/constants.py` to new values from `weights.py:DEFAULT_WEIGHTS` (single source of truth — `constants.py` re-exports from `weights.py`).
- Update `docs/transition-scoring.md` to match new structure + new weights + new section-aware behavior.

After commit 6: `make check` (lint + typecheck + full test suite) must pass.

---

## Tests

Test files mirror the new module structure:

```text
tests/test_domain/test_transition/
├── test_weights.py             (NEW: invariants — sum=1.0, types, ranges)
├── test_hard_constraints.py    (extract from test_transition.py)
├── test_components/
│   ├── test_bpm.py
│   ├── test_harmonic.py        (drum-only pair relaxation cases)
│   ├── test_energy.py
│   ├── test_spectral.py
│   ├── test_groove.py
│   └── test_timbral.py
├── test_section_context.py     (NEW)
├── test_style.py               (move test_transition_style.py here)
└── test_scorer.py              (orchestration only — verifies scorer
                                 calls components and applies weights)

tests/test_services/
└── test_mix_point_service.py   (NEW: with seeded beatgrid + sections)
```

Existing tests under `tests/test_services/test_transition_*.py` and `tests/test_domain/test_transition_style.py` continue to pass with **no edits** (public API frozen). After commit 6, they're moved to the new structure but their assertions are unchanged.

**New ground-truth assertions** (commit 5):

- Two atonal techno tracks with `from_section=OUTRO`, `to_section=INTRO` and Camelot distance 4 → `harmonic_score ≥ 0.85` (would be ~0.10 today).
- Same pair without `section_context` → `harmonic_score ≈ 0.10` (today's behavior preserved when context absent).
- Drum-only pair: weighted sum uses `DRUM_ONLY_WEIGHT_OVERRIDE`, so `harmonic` contributes 0.05 not 0.20.

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Recalibrated weights change scores for existing sets → user confusion | DEFAULT_WEIGHTS change is the most user-visible part. Document it explicitly in commit 6 message + CHANGELOG entry. Old saved transitions in DB are not re-scored automatically. |
| `recommend_style` thresholds were tuned by hand; changes might surprise panel | Thresholds stay at current values (0.45/0.40/0.55/0.95/0.85/0.75). Only the *capability* to override them is added (`StyleRules` dataclass). Default behavior unchanged. |
| MixPointService is slow (downbeats × sections) and blocks `deliver_set` | Run it once per set version, persist results. Build/rebuild paths skip it entirely (only `deliver_set` triggers). |
| Section-aware override might incorrectly suppress harmonic for tracks that *do* have melodic intros | `is_drum_only_pair` requires BOTH sides be in {INTRO, OUTRO, SUSTAIN, AMBIENT}. Tracks with melodic intros usually have ATTACK/BUILD as their first section, so they don't qualify. Edge cases logged for review. |
| 6 commits might introduce regression in commit N that's only caught in commit N+M | Each commit must keep `make check` green. Tests are added per-commit, not back-loaded. |
| `DEFAULT_TRANSITION_WEIGHTS` lives in `app/core/constants.py` AND `app/domain/transition/weights.py` — divergence | `constants.py` becomes a thin re-export: `from app.domain.transition.weights import DEFAULT_WEIGHTS as DEFAULT_TRANSITION_WEIGHTS`. Single source of truth. |
| Lazy imports inside `scorer.py` violate `tools.md` "no lazy imports" rule | Fixed in commit 3: `bpm_distance` is hoisted to module top in each component file. |
| `recommend_style` is called on synthetic `TransitionScore` reconstructed from DB row (`set/scoring.py:63`) — must keep working on partial scores | `recommend_style` only reads public fields of `TransitionScore` — preserved by design. Test asserts this contract. |

---

## Open Questions

None for current scope. The following are explicitly **deferred** to future iterations:

1. **Continuous harmonic distance** as primary metric (Bibbó & Faraldo 2022). Tonnetz cosine is already used at 30% weight; promoting it to primary requires a wider study and ground-truth re-calibration. Out of scope for this redesign.
2. **Stem-aware bass swap** scoring. Requires stem separation pipeline (not currently in audio analyzers). Out of scope.
3. **Loudness on mix-region windows** instead of integrated full-track. Requires loading audio at scoring time (currently scoring is purely DB-driven). Out of scope.
4. **Per-template `StyleRules`** (different cutoffs for warm_up vs peak_hour). Infrastructure is added (StyleRules dataclass), but default rules are the only ones used. Future work can override per-template.

---

## Acceptance Criteria

After commit 6:

- [ ] `app/domain/transition/scorer.py` is ≤ 100 lines (was 538).
- [ ] All magic numbers from `_score_*` methods live in `weights.py`. `grep -E '\b[0-9]+\.[0-9]+\b' app/domain/transition/scorer.py` returns nothing meaningful.
- [ ] `make check` passes (ruff, mypy strict, full pytest suite).
- [ ] Public imports unchanged: `from app.domain.transition import TransitionScorer, TransitionScore, recommend_style, style_profile` works.
- [ ] `scorer.score(a, b)` (no kwargs) returns identical scores to before (within float precision) **when `section_context=None`** and weights left at defaults.
- [ ] New tests for section-aware harmonic relaxation pass.
- [ ] `MixPointService` can populate `mix_in_point_ms`/`mix_out_point_ms` for a seeded set with beatgrid + sections.
- [ ] `docs/transition-scoring.md` reflects current code: 6 components with correct weights, all sub-weights documented, recommend_style decision tree matches `style.py`.
- [ ] `infer_intent` v2 returns identical results to v1 when `template=None`.
- [ ] Panel waveform player still receives `recommended_style` + `recommended_bars` in the same response shape (verified via `app/services/set/scoring.py` integration test).

---

## Timeline (no estimates per project rules — just ordering)

1. weights.py extraction
2. score.py + hard_constraints.py extraction
3. components/ extraction (the bulk of the refactor)
4. style.py + StyleRules extraction
5. Section-aware scoring (the one new feature)
6. MixPointService + intent v2 + docs sync

Each step is independently committable and `make check`-clean. Work proceeds in order; no parallel branches.
