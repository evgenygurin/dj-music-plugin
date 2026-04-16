---
description: Transition scoring — 6-component formula, Camelot wheel, TransitionIntent
globs:
  - app/transition/**/*.py
  - app/camelot/**/*.py
---

# Transition Scoring

Pure domain logic. No I/O, no DB, no async. All in `app/transition/`.

## TransitionScorer

```python
from app.transition.scorer import TransitionScorer, TransitionScore

scorer = TransitionScorer()  # default weights from settings
score: TransitionScore = scorer.score(from_features, to_features, intent=TransitionIntent.MAINTAIN)
```

Input: two `TrackFeatures` dataclasses. Output: `TransitionScore`.
Always check `score.hard_reject` before using `score.total`.

## 6 Components (default weights, sum = 1.0)

Source of truth: `app/core/constants.py:DEFAULT_TRANSITION_WEIGHTS`

| Component | Weight | Key inputs |
|-----------|--------|-----------|
| BPM | 0.20 | `bpm`, `bpm_stability`, `bpm_confidence` |
| Harmonic | 0.12 | `key_code` → `camelot_distance()`, `atonality`, `key_confidence` |
| Energy | 0.18 | `integrated_lufs`, `energy_mean`, `short_term_lufs_mean` |
| Spectral | 0.20 | `spectral_centroid_hz`, `spectral_flatness`, `mfcc_vector` |
| Groove | 0.15 | `onset_rate`, `kick_prominence`, `pulse_clarity` |
| Timbral | 0.15 | `hnr_db`, `chroma_entropy`, `dynamic_complexity` |

## Hard Constraints (gate before scoring)

`check_hard_constraints()` rejects pairs before any scoring:
- BPM diff > `settings.transition_hard_reject_bpm_diff` → `hard_reject=True`
- Camelot distance ≥ `settings.transition_hard_reject_camelot_dist` → `hard_reject=True`

## Camelot Distance

```python
from app.camelot.wheel import camelot_distance

dist = camelot_distance(from_key_code, to_key_code)  # 0=same, 1=adjacent, 7=max clash
```

`key_code` 0–23: 0–11 = major, 12–23 = minor.

## TransitionIntent

```python
from app.transition.types import TransitionIntent     # MAINTAIN, RAMP_UP, COOL_DOWN, CONTRAST
from app.transition.intent import infer_intent, INTENT_WEIGHT_MODIFIERS

intent = infer_intent(set_position=0.3, energy_delta_lufs=1.5, template=SetTemplate.CLASSIC_60)
```

`infer_intent()` auto-detects from set position + energy delta. Template shifts phase boundaries.

Weight modifiers per intent:
- `MAINTAIN`: BPM 0.28, harmonic 0.18 — prioritize flow
- `RAMP_UP`: energy 0.30, harmonic 0.25 — build tension
- `COOL_DOWN`: energy 0.25, BPM 0.20 — smooth descent
- `CONTRAST`: spectral 0.20, timbral 0.20 — maximize variety

## TransitionScore Fields

`total: float`, per-component `bpm/harmonic/energy/spectral/groove/timbral: float`,
`hard_reject: bool`, `reject_reason: str | None`, `soft_conflicts: list[str]`

## Gotchas

- `TransitionScorer` does NOT access DB — requires pre-loaded `TrackFeatures` objects
- Missing features (`None`) fall back to neutral score (0.5), not zero — do not pre-filter None features
- `VOCAL_PITCH_SALIENCE_THRESHOLD`: tracks above it get modified timbral scoring (detects vocals)
- `DRUM_ONLY_WEIGHT_OVERRIDE`: short tracks without harmonic content → BPM weight boosted
- `bpm_distance()` in `app/transition/math_helpers` handles half-tempo doubling (75 BPM vs 150 BPM = dist 0, not 75)
- Components are in `app/transition/components/` (one module per component) — scorer imports and combines them
