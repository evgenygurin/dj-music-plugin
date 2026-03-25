# Transition Scoring

5-component weighted formula for evaluating track-to-track transitions.

## Formula

```text
score = w_bpm * S_bpm + w_harmonic * S_harmonic + w_energy * S_energy
      + w_spectral * S_spectral + w_groove * S_groove
```

Default weights (from `app/core/constants.py`):

| Component | Weight | Purpose |
|-----------|--------|---------|
| BPM | 0.25 | Tempo compatibility |
| Harmonic | 0.20 | Key compatibility (Camelot) |
| Energy | 0.25 | Energy flow (LUFS) |
| Spectral | 0.15 | Timbral similarity |
| Groove | 0.15 | Rhythmic compatibility |

## Hard Constraints

If ANY violated → score = 0.0 (hard reject):

| Constraint | Threshold | Config Key |
|-----------|-----------|-----------|
| BPM difference > N | 10 BPM | `settings.transition_hard_reject_bpm_diff` |
| Camelot distance ≥ N | 5 | `settings.transition_hard_reject_camelot_dist` |
| Energy gap > N LUFS | 6.0 LUFS | `settings.transition_hard_reject_energy_gap` |

## Component Details

### S_bpm — Tempo Compatibility

Gaussian similarity with double/half-time awareness:

```text
delta = |bpm_a - bpm_b|
# Check double/half-time
delta = min(delta, |bpm_a - bpm_b*2|, |bpm_a - bpm_b/2|)
S_bpm = exp(-delta² / (2 * sigma²))   # sigma tuned for ~3 BPM tolerance
```

### S_harmonic — Key Compatibility

Camelot wheel distance, weighted by chroma quality:

```text
dist = camelot_distance(key_a, key_b)  # 0-6
base = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1, 5+: 0.0}[dist]
# Weight by confidence and tonality
S_harmonic = base * (1 - chroma_entropy_a/max) * sqrt(hnr_a * hnr_b)
```

### S_energy — Energy Flow

Sigmoid function on LUFS difference:

```text
delta = lufs_b - lufs_a  # positive = energy goes up
S_energy = sigmoid(delta, center=0, spread=3)
# Slight preference for energy increase (DJ build)
```

### S_spectral — Timbral Similarity

Three sub-components:

```text
mfcc_sim = cosine_similarity(mfcc_a, mfcc_b)
centroid_sim = 1 - |centroid_a - centroid_b| / max_centroid
band_balance = correlation(energy_bands_a, energy_bands_b)
S_spectral = 0.4 * mfcc_sim + 0.3 * centroid_sim + 0.3 * band_balance
```

### S_groove — Rhythmic Compatibility

```text
onset_match = 1 - |onset_rate_a - onset_rate_b| / max(onset_rate_a, onset_rate_b)
kick_match = 1 - |kick_prominence_a - kick_prominence_b|
S_groove = 0.5 * onset_match + 0.5 * kick_match
```

## Camelot Wheel

24 keys arranged in a circle. Adjacent keys are harmonically compatible.

```text
        12B(E)
    11B(A)   1B(B)
  10B(D)       2B(F#)
 9B(G)           3B(Db)
  8B(C)        4B(Ab)
    7B(F)    5B(Eb)
        6B(Bb)

        12A(Dbm)
    11A(F#m)   1A(Abm)
  10A(Bm)        2A(Ebm)
 9A(Em)            3A(Bbm)
  8A(Am)         4A(Fm)
    7A(Dm)     5A(Cm)
        6A(Gm)
```

Compatible transitions (distance ≤ 1):
- Same position: 8A → 8A (same key)
- ±1 on wheel: 8A → 7A, 8A → 9A (adjacent keys)
- A↔B same number: 8A → 8B (relative major/minor)

## Feature Loading

`TrackFeatures.from_db(row)` classmethod constructs the dataclass from a `TrackAudioFeaturesComputed` DB row — single source of truth for field mapping.

```python
# Single track
feat = await feat_repo.get_scoring_features(track_id)   # returns TrackFeatures | None

# Batch (N SQL → 1 SQL) — use in loops
features_map = await feat_repo.get_scoring_features_batch(track_ids)
feat = features_map.get(tid, TrackFeatures())  # default empty if no features
```

Both methods live in `app/repositories/feature.py`.

## Transition Cache

LRU cache for computed scores:

```text
Key: (track_id_a, track_id_b)   # ordered tuple
Value: TransitionScore (5 components + overall)
TTL: settings.transition_cache_ttl (default 3600s)
Max size: settings.transition_cache_max_size (default 10,000)
Invalidation: when audio features of either track change
```

## Optimization: Pruning Candidate Pairs

For 3000 tracks, naive O(n²) = 9M pairs. Pruning strategy:

1. **BPM index**: only consider tracks within ±10 BPM → ~30% of library
2. **Key index**: only compatible Camelot keys → ~40%
3. **Energy filter**: only within ±6 LUFS → ~50%
4. Combined: 9M × 0.3 × 0.4 × 0.5 ≈ **540K pairs**
