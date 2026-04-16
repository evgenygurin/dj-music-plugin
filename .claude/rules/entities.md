---
description: Domain entity dataclasses — TrackFeatures, pure domain layer, no DB/HTTP
globs: app/entities/**/*.py
---

# Domain Entities

Pure dataclasses. No DB, no HTTP, no ORM. In `app/entities/` — importable from any layer without circular dependencies.

## TrackFeatures (`app/entities/audio/features.py`)

Minimal feature set for transition scoring and optimization.

```python
from app.entities.audio.features import TrackFeatures

# From DB row
features = TrackFeatures.from_db(row)     # row = TrackAudioFeaturesComputed ORM instance

# Manual
features = TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.5)
```

All fields optional: `float | None`, `int | None`, `list[float] | None`, `bool | None`.
Missing features are safe — scorers handle `None` with neutral fallback (0.5).

## Field Groups

| Group | Fields |
|-------|--------|
| Core | `bpm`, `key_code`, `integrated_lufs`, `energy_mean`, `onset_rate`, `kick_prominence` |
| Spectral | `spectral_centroid_hz`, `spectral_flatness`, `mfcc_vector` (list), `energy_bands` (6 floats) |
| Groove | `onset_rate`, `kick_prominence`, `pulse_clarity`, `hp_ratio`, `chroma_entropy` |
| Timbral | `hnr_db`, `chroma_entropy`, `dynamic_complexity` |
| P3 BPM | `bpm_confidence`, `variable_tempo`, `bpm_histogram_first_peak_weight`, `bpm_histogram_second_peak_bpm` |
| P3 Harmonic | `atonality`, `key_confidence` |
| P3 Energy | `short_term_lufs_mean`, `loudness_range_lu`, `crest_factor_db`, `energy_slope` |
| P3 Spectral | `spectral_rolloff_85`, `spectral_rolloff_95`, `spectral_slope`, `spectral_flux_std` |
| P3 Groove | `pulse_clarity`, `hp_ratio`, `tempogram_ratio_vector` |
| Beatgrid | `first_downbeat_ms` — first downbeat position in **milliseconds** from track start |
| Mood | `mood: str | None` — for filtering/reasoning, NOT used by TransitionScorer |

## `from_db()` Quirks

- `mfcc_vector`, `tonnetz_vector`, `beat_loudness_band_ratio`, `tempogram_ratio_vector`: stored as JSON strings in DB, auto-parsed on load
- `energy_bands`: assembled from 6 separate columns (`energy_sub`, `energy_low`, `energy_lowmid`, `energy_mid`, `energy_highmid`, `energy_high`)
- If any of the 6 band columns is `None` → `energy_bands = None` (requires all present)

## Gotchas

- `TrackFeatures` has NO `track_id` field — it's stateless. Callers maintain `id → TrackFeatures` mapping
- `first_downbeat_ms` is in **milliseconds**, not seconds — convert before audio math
- `mood` is NOT used in `TransitionScorer` — higher-level filtering/reasoning only
- Do NOT add DB model imports or ORM to `app/entities/` — pure domain layer
- `energy_bands` field is a list of 6 floats in this order: sub, low, lowmid, mid, highmid, high
