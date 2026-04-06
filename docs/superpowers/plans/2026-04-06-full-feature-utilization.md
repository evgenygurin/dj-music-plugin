# Full Audio Feature Utilization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use all 55 audio features from `track_audio_features_computed` across scoring, classifier, export, and panel — zero unused fields.

**Architecture:** Four independent phases: (1) Scoring enrichment — add 15 features to TrackFeatures + 6 scoring components, (2) Classifier & audit — add features to subgenre profiles + audit checks, (3) Export — extend M3U8/JSON/cheat sheet/Rekordbox, (4) Panel — extend dashboard charts + track detail tabs. Each phase is independently testable and committable.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, pytest, FastMCP, Next.js 16, Recharts, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-06-full-feature-utilization-design.md`

---

## Phase 1: Scoring Enrichment (19 → 34 features)

### Task 1: Extend TrackFeatures dataclass with 15 new fields

**Files:**
- Modify: `app/core/track_features.py`
- Test: `tests/test_services/test_transition.py`

- [ ] **Step 1: Write failing test for new fields in TrackFeatures**

Add to `tests/test_services/test_transition.py`:

```python
class _FullRow:
    """Mimics TrackAudioFeaturesComputed with all scoring fields."""
    bpm = 128.0
    key_code = 14
    integrated_lufs = -8.0
    spectral_centroid_hz = 3000.0
    spectral_flatness = 0.1
    energy_mean = 0.6
    onset_rate = 4.0
    kick_prominence = 0.5
    hnr_db = 12.0
    chroma_entropy = 2.5
    mfcc_vector = "[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.1, 0.2, 0.3]"
    energy_sub = 0.1
    energy_low = 0.2
    energy_lowmid = 0.15
    energy_mid = 0.15
    energy_highmid = 0.1
    energy_high = 0.05
    dissonance_mean = 0.3
    danceability = 1.2
    tonnetz_vector = "[0.1, 0.2, -0.1, 0.0, 0.15, -0.05]"
    beat_loudness_band_ratio = "[0.3, 0.5, 0.2]"
    spectral_complexity_mean = 25.0
    pitch_salience_mean = 0.7
    bpm_stability = 0.95
    spectral_contrast = 18.0
    # New P3 fields
    bpm_confidence = 0.98
    variable_tempo = False
    bpm_histogram_first_peak_weight = 0.85
    bpm_histogram_second_peak_bpm = 256.0
    bpm_histogram_second_peak_weight = 0.1
    atonality = False
    key_confidence = 0.75
    short_term_lufs_mean = -9.5
    loudness_range_lu = 8.0
    crest_factor_db = 12.0
    energy_slope = 0.02
    spectral_rolloff_85 = 4500.0
    spectral_rolloff_95 = 8000.0
    spectral_slope = -0.003
    spectral_flux_std = 0.05
    pulse_clarity = 0.85
    hp_ratio = 2.5
    tempogram_ratio_vector = "[0.8, 0.1, 0.05, 0.05]"
    dynamic_complexity = 4.0

def test_from_db_maps_new_p3_fields() -> None:
    """from_db() must map all 15 new scoring fields."""
    row = _FullRow()
    feat = TrackFeatures.from_db(row)
    assert feat.bpm_confidence == 0.98
    assert feat.variable_tempo is False
    assert feat.bpm_histogram_first_peak_weight == 0.85
    assert feat.bpm_histogram_second_peak_bpm == 256.0
    assert feat.atonality is False
    assert feat.key_confidence == 0.75
    assert feat.short_term_lufs_mean == -9.5
    assert feat.loudness_range_lu == 8.0
    assert feat.crest_factor_db == 12.0
    assert feat.energy_slope == 0.02
    assert feat.spectral_rolloff_85 == 4500.0
    assert feat.spectral_rolloff_95 == 8000.0
    assert feat.spectral_slope == -0.003
    assert feat.spectral_flux_std == 0.05
    assert feat.pulse_clarity == 0.85
    assert feat.hp_ratio == 2.5
    assert feat.tempogram_ratio_vector is not None
    assert len(feat.tempogram_ratio_vector) == 4
    assert feat.dynamic_complexity == 4.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_transition.py::test_from_db_maps_new_p3_fields -v`
Expected: FAIL — `TrackFeatures` has no `bpm_confidence` field

- [ ] **Step 3: Add 15 new fields to TrackFeatures dataclass**

In `app/core/track_features.py`, add after the `spectral_contrast` field:

```python
    # P3 enrichment: BPM
    bpm_confidence: float | None = None
    variable_tempo: bool | None = None
    bpm_histogram_first_peak_weight: float | None = None
    bpm_histogram_second_peak_bpm: float | None = None

    # P3 enrichment: Harmonic
    atonality: bool | None = None
    key_confidence: float | None = None

    # P3 enrichment: Energy
    short_term_lufs_mean: float | None = None
    loudness_range_lu: float | None = None
    crest_factor_db: float | None = None
    energy_slope: float | None = None

    # P3 enrichment: Spectral
    spectral_rolloff_85: float | None = None
    spectral_rolloff_95: float | None = None
    spectral_slope: float | None = None
    spectral_flux_std: float | None = None

    # P3 enrichment: Groove
    pulse_clarity: float | None = None
    hp_ratio: float | None = None
    tempogram_ratio_vector: list[float] | None = None

    # P3 enrichment: Timbral
    dynamic_complexity: float | None = None
```

Update `from_db()` to map these fields — add inside the `return cls(...)` call:

```python
            bpm_confidence=getattr(row, "bpm_confidence", None),
            variable_tempo=getattr(row, "variable_tempo", None),
            bpm_histogram_first_peak_weight=getattr(row, "bpm_histogram_first_peak_weight", None),
            bpm_histogram_second_peak_bpm=getattr(row, "bpm_histogram_second_peak_bpm", None),
            atonality=getattr(row, "atonality", None),
            key_confidence=getattr(row, "key_confidence", None),
            short_term_lufs_mean=getattr(row, "short_term_lufs_mean", None),
            loudness_range_lu=getattr(row, "loudness_range_lu", None),
            crest_factor_db=getattr(row, "crest_factor_db", None),
            energy_slope=getattr(row, "energy_slope", None),
            spectral_rolloff_85=getattr(row, "spectral_rolloff_85", None),
            spectral_rolloff_95=getattr(row, "spectral_rolloff_95", None),
            spectral_slope=getattr(row, "spectral_slope", None),
            spectral_flux_std=getattr(row, "spectral_flux_std", None),
            pulse_clarity=getattr(row, "pulse_clarity", None),
            hp_ratio=getattr(row, "hp_ratio", None),
            tempogram_ratio_vector=tempogram,
            dynamic_complexity=getattr(row, "dynamic_complexity", None),
```

Also add the tempogram JSON parsing near the other vector parsers:

```python
        # Parse tempogram_ratio_vector from JSON
        tempogram = None
        raw_tempogram = getattr(row, "tempogram_ratio_vector", None)
        if raw_tempogram:
            tempogram = json.loads(raw_tempogram) if isinstance(raw_tempogram, str) else raw_tempogram
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_transition.py::test_from_db_maps_new_p3_fields -v`
Expected: PASS

- [ ] **Step 5: Run all existing scoring tests to verify no regression**

Run: `uv run pytest tests/test_services/test_transition.py tests/test_services/test_transition_scoring_p2.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/core/track_features.py tests/test_services/test_transition.py
git commit -m "feat(scoring): extend TrackFeatures with 15 new fields for P3 enrichment"
```

---

### Task 2: Add settings for new scoring thresholds

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Add new settings**

In `app/config.py`, in the `Settings` class after existing transition settings:

```python
    # ── P3 Scoring Thresholds ─────────────────────────
    scoring_bpm_confidence_floor: float = 0.5  # below this, BPM score reduced
    scoring_variable_tempo_penalty: float = 0.15  # penalty for variable tempo tracks
    scoring_lra_diff_penalty_threshold: float = 8.0  # LU difference for penalty
    scoring_lra_diff_penalty: float = 0.10  # penalty amount
    scoring_crest_diff_penalty_threshold: float = 10.0  # dB difference for penalty
    scoring_crest_diff_penalty: float = 0.10  # penalty amount
    scoring_energy_slope_bonus: float = 0.05  # bonus for same slope direction
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat(config): add P3 scoring threshold settings"
```

---

### Task 3: Enrich BPM scoring component (2 → 5 features)

**Files:**
- Modify: `app/services/transition.py`
- Test: `tests/test_services/test_transition_scoring_p3.py` (create)

- [ ] **Step 1: Write failing tests for BPM enrichment**

Create `tests/test_services/test_transition_scoring_p3.py`:

```python
"""Tests for P3 scoring enrichments — full feature utilization."""

from __future__ import annotations

import pytest

from app.core.track_features import TrackFeatures
from app.services.transition import TransitionScorer

def _base(**overrides: object) -> TrackFeatures:
    """Minimal valid features for scoring (no hard reject)."""
    defaults: dict[str, object] = {
        "bpm": 130.0,
        "key_code": 0,
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 2000.0,
        "spectral_flatness": 0.2,
        "energy_mean": 0.5,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": 5.0,
        "chroma_entropy": 3.0,
        "mfcc_vector": [0.1] * 13,
        "energy_bands": [0.1, 0.2, 0.15, 0.15, 0.1, 0.05],
    }
    defaults.update(overrides)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]

# ── BPM confidence ────────────────────────────────────

class TestBpmConfidence:
    def test_low_confidence_reduces_bpm_score(self) -> None:
        scorer = TransitionScorer()
        a_high = _base(bpm_confidence=0.95)
        b_high = _base(bpm_confidence=0.95, bpm=131.0)
        score_high = scorer.score(a_high, b_high)

        a_low = _base(bpm_confidence=0.3)
        b_low = _base(bpm_confidence=0.3, bpm=131.0)
        score_low = scorer.score(a_low, b_low)

        assert score_high.bpm > score_low.bpm

    def test_none_confidence_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base(bpm_confidence=None)
        b = _base(bpm_confidence=None)
        result = scorer.score(a, b)
        assert result.bpm > 0.9  # identical BPM

class TestVariableTempo:
    def test_variable_tempo_penalizes(self) -> None:
        scorer = TransitionScorer()
        a_var = _base(variable_tempo=True)
        b_var = _base(variable_tempo=False)
        score_var = scorer.score(a_var, b_var)

        a_fixed = _base(variable_tempo=False)
        b_fixed = _base(variable_tempo=False)
        score_fixed = scorer.score(a_fixed, b_fixed)

        assert score_fixed.bpm > score_var.bpm

    def test_none_variable_tempo_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base(variable_tempo=None)
        b = _base(variable_tempo=None)
        result = scorer.score(a, b)
        assert result.bpm > 0.9

class TestBpmHistogram:
    def test_polyrhythmic_uses_second_peak(self) -> None:
        """Low first_peak_weight + second_peak_bpm close to target → no hard reject."""
        scorer = TransitionScorer()
        # Track A at 128 BPM but polyrhythmic — second peak at 64 BPM
        a = _base(bpm=128.0, bpm_histogram_first_peak_weight=0.4,
                  bpm_histogram_second_peak_bpm=64.0)
        # Track B at 64 BPM — normally hard reject (diff=64), but half-time = 0
        b = _base(bpm=64.0)
        result = scorer.score(a, b)
        # Should NOT hard reject due to double/half-time awareness
        assert result.bpm > 0.5 or not result.hard_reject
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py -v -k "Bpm or Variable or Histogram"`
Expected: FAIL — methods don't use bpm_confidence yet

- [ ] **Step 3: Implement BPM enrichment**

In `app/services/transition.py`, update `_score_bpm`:

```python
    def _score_bpm(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.bpm is None or to_t.bpm is None:
            return 0.5  # unknown = neutral
        delta = self._bpm_distance(from_t.bpm, to_t.bpm)
        sigma = 3.0  # ~3 BPM tolerance
        score = math.exp(-(delta**2) / (2 * sigma**2))

        # BPM stability factor: unstable tempo makes mixing harder
        if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
            stability = min(from_t.bpm_stability, to_t.bpm_stability)
            score *= max(0.7, stability)  # up to 30% penalty for unstable BPM

        # BPM confidence factor: low confidence = less reliable BPM
        if from_t.bpm_confidence is not None and to_t.bpm_confidence is not None:
            min_conf = min(from_t.bpm_confidence, to_t.bpm_confidence)
            if min_conf < settings.scoring_bpm_confidence_floor:
                score *= max(0.7, min_conf / settings.scoring_bpm_confidence_floor)

        # Variable tempo penalty
        if (from_t.variable_tempo is True) or (to_t.variable_tempo is True):
            score = max(0.0, score - settings.scoring_variable_tempo_penalty)

        return score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py -v -k "Bpm or Variable or Histogram"`
Expected: PASS

- [ ] **Step 5: Run all scoring tests for regression**

Run: `uv run pytest tests/test_services/test_transition.py tests/test_services/test_transition_scoring_p2.py tests/test_services/test_transition_scoring_p3.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich BPM component with confidence, variable_tempo, histogram"
```

---

### Task 4: Enrich Harmonic scoring component (3 → 6 features)

**Files:**
- Modify: `app/services/transition.py`
- Modify: `tests/test_services/test_transition_scoring_p3.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services/test_transition_scoring_p3.py`:

```python
# ── Harmonic enrichment ───────────────────────────────

class TestAtonalityEnrichment:
    def test_both_atonal_relaxes_harmonic(self) -> None:
        scorer = TransitionScorer()
        # Both atonal, distant keys — should be relaxed
        a = _base(key_code=0, atonality=True)
        b = _base(key_code=8, atonality=True)  # distance=4
        score_atonal = scorer.score(a, b)

        a_tonal = _base(key_code=0, atonality=False)
        b_tonal = _base(key_code=8, atonality=False)
        score_tonal = scorer.score(a_tonal, b_tonal)

        assert score_atonal.harmonic > score_tonal.harmonic

    def test_one_atonal_no_relaxation(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_code=0, atonality=True)
        b = _base(key_code=8, atonality=False)
        score_mixed = scorer.score(a, b)

        a_both = _base(key_code=0, atonality=False)
        b_both = _base(key_code=8, atonality=False)
        score_tonal = scorer.score(a_both, b_both)

        # Mixed should be similar to both tonal (no relaxation)
        assert abs(score_mixed.harmonic - score_tonal.harmonic) < 0.15

class TestKeyConfidenceEnrichment:
    def test_low_key_confidence_relaxes(self) -> None:
        scorer = TransitionScorer()
        # Distant keys, but low confidence
        a = _base(key_code=0, key_confidence=0.3)
        b = _base(key_code=6, key_confidence=0.3)
        score_low = scorer.score(a, b)

        a_high = _base(key_code=0, key_confidence=0.9)
        b_high = _base(key_code=6, key_confidence=0.9)
        score_high = scorer.score(a_high, b_high)

        # Low confidence → relaxed penalty
        assert score_low.harmonic >= score_high.harmonic

    def test_none_key_confidence_no_change(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_confidence=None)
        b = _base(key_confidence=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.harmonic <= 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py -v -k "Atonal or KeyConfidence"`
Expected: FAIL

- [ ] **Step 3: Implement harmonic enrichment**

In `app/services/transition.py`, update `_score_harmonic`:

```python
    def _score_harmonic(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.key_code is None or to_t.key_code is None:
            return 0.5
        dist = camelot_distance(from_t.key_code, to_t.key_code)
        base_scores = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
        base = base_scores.get(dist, 0.0)

        # Both atonal → key less important, relax to 0.8 floor
        if from_t.atonality is True and to_t.atonality is True:
            base = max(0.8, base)

        # Weight by HNR
        hnr_factor = 1.0
        if from_t.hnr_db is not None and to_t.hnr_db is not None:
            avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
            hnr_factor = max(0.5, min(1.0, (avg_hnr + 30) / 30))

        score = base * hnr_factor

        # Key confidence: low confidence → blend toward neutral
        if from_t.key_confidence is not None and to_t.key_confidence is not None:
            min_conf = min(from_t.key_confidence, to_t.key_confidence)
            if min_conf < 0.5:
                score = score * min_conf / 0.5 + 0.5 * (1 - min_conf / 0.5)

        # Tonnetz cosine similarity (30% weight when available)
        if from_t.tonnetz_vector and to_t.tonnetz_vector:
            tonnetz_cos = self._cosine_similarity(from_t.tonnetz_vector, to_t.tonnetz_vector)
            score = 0.70 * score + 0.30 * tonnetz_cos

        return score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py -v -k "Atonal or KeyConfidence"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich harmonic with atonality relaxation and key confidence"
```

---

### Task 5: Enrich Energy scoring component (1 → 5 features)

**Files:**
- Modify: `app/services/transition.py`
- Modify: `tests/test_services/test_transition_scoring_p3.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services/test_transition_scoring_p3.py`:

```python
# ── Energy enrichment ─────────────────────────────────

class TestEnergyEnrichment:
    def test_lra_diff_penalizes(self) -> None:
        scorer = TransitionScorer()
        a = _base(loudness_range_lu=4.0)
        b = _base(loudness_range_lu=14.0)  # diff=10 > 8
        score_diff = scorer.score(a, b)

        a_sim = _base(loudness_range_lu=5.0)
        b_sim = _base(loudness_range_lu=6.0)  # diff=1
        score_sim = scorer.score(a_sim, b_sim)

        assert score_sim.energy >= score_diff.energy

    def test_crest_diff_penalizes(self) -> None:
        scorer = TransitionScorer()
        a = _base(crest_factor_db=5.0)
        b = _base(crest_factor_db=18.0)  # diff=13 > 10
        score_diff = scorer.score(a, b)

        a_sim = _base(crest_factor_db=10.0)
        b_sim = _base(crest_factor_db=11.0)
        score_sim = scorer.score(a_sim, b_sim)

        assert score_sim.energy >= score_diff.energy

    def test_same_energy_slope_bonus(self) -> None:
        scorer = TransitionScorer()
        # Both rising energy
        a_up = _base(energy_slope=0.05)
        b_up = _base(energy_slope=0.03)
        score_same = scorer.score(a_up, b_up)

        # Opposite slopes
        a_up2 = _base(energy_slope=0.05)
        b_down = _base(energy_slope=-0.05)
        score_opp = scorer.score(a_up2, b_down)

        assert score_same.energy >= score_opp.energy

    def test_none_energy_extras_no_change(self) -> None:
        scorer = TransitionScorer()
        a = _base(loudness_range_lu=None, crest_factor_db=None, energy_slope=None)
        b = _base(loudness_range_lu=None, crest_factor_db=None, energy_slope=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.energy <= 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestEnergyEnrichment -v`
Expected: FAIL

- [ ] **Step 3: Implement energy enrichment**

In `app/services/transition.py`, update `_score_energy`:

```python
    def _score_energy(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
            return 0.5
        delta = to_t.integrated_lufs - from_t.integrated_lufs
        # Sigmoid centered at 0, slight preference for energy increase
        score = 1.0 / (1.0 + math.exp(-delta / 3.0))

        # Loudness range penalty: hard to mix tracks with very different LRA
        if from_t.loudness_range_lu is not None and to_t.loudness_range_lu is not None:
            lra_diff = abs(from_t.loudness_range_lu - to_t.loudness_range_lu)
            if lra_diff > settings.scoring_lra_diff_penalty_threshold:
                score = max(0.0, score - settings.scoring_lra_diff_penalty)

        # Crest factor penalty: different dynamic ranges = rough transition
        if from_t.crest_factor_db is not None and to_t.crest_factor_db is not None:
            crest_diff = abs(from_t.crest_factor_db - to_t.crest_factor_db)
            if crest_diff > settings.scoring_crest_diff_penalty_threshold:
                score = max(0.0, score - settings.scoring_crest_diff_penalty)

        # Energy slope bonus: same direction = smoother flow
        if from_t.energy_slope is not None and to_t.energy_slope is not None:
            if (from_t.energy_slope > 0) == (to_t.energy_slope > 0):
                score = min(1.0, score + settings.scoring_energy_slope_bonus)

        return score
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestEnergyEnrichment -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich energy with LRA, crest factor, and slope"
```

---

### Task 6: Enrich Spectral scoring component (5 → 8 features)

**Files:**
- Modify: `app/services/transition.py`
- Modify: `tests/test_services/test_transition_scoring_p3.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services/test_transition_scoring_p3.py`:

```python
# ── Spectral enrichment ───────────────────────────────

class TestSpectralEnrichment:
    def test_similar_rolloff_boosts(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_rolloff_85=4000.0, spectral_rolloff_95=8000.0)
        b = _base(spectral_rolloff_85=4100.0, spectral_rolloff_95=8100.0)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_rolloff_85=2000.0, spectral_rolloff_95=4000.0)
        b_diff = _base(spectral_rolloff_85=8000.0, spectral_rolloff_95=16000.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.spectral >= score_diff.spectral

    def test_similar_slope_boosts(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_slope=-0.003)
        b = _base(spectral_slope=-0.004)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_slope=-0.001)
        b_diff = _base(spectral_slope=-0.01)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.spectral >= score_diff.spectral

    def test_none_spectral_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_rolloff_85=None, spectral_slope=None, spectral_flux_std=None)
        b = _base(spectral_rolloff_85=None, spectral_slope=None, spectral_flux_std=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.spectral <= 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestSpectralEnrichment -v`
Expected: FAIL

- [ ] **Step 3: Implement spectral enrichment**

In `app/services/transition.py`, update `_score_spectral` — replace the averaging approach with weighted sub-scores:

```python
    def _score_spectral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        signals: list[float] = []
        weights: list[float] = []

        # MFCC cosine similarity (30%)
        if from_t.mfcc_vector and to_t.mfcc_vector:
            cos_sim = self._cosine_similarity(from_t.mfcc_vector, to_t.mfcc_vector)
            signals.append(cos_sim)
            weights.append(0.30)

        # Centroid proximity (20%)
        if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
            max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
            centroid_sim = 1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c
            signals.append(max(0.0, centroid_sim))
            weights.append(0.20)

        # Energy band balance (20%)
        if from_t.energy_bands and to_t.energy_bands:
            correlation = self._correlation(from_t.energy_bands, to_t.energy_bands)
            signals.append(max(0.0, correlation))
            weights.append(0.20)

        # Rolloff similarity (15%) — average of 85% and 95%
        rolloff_vals: list[float] = []
        if from_t.spectral_rolloff_85 is not None and to_t.spectral_rolloff_85 is not None:
            max_r = max(from_t.spectral_rolloff_85, to_t.spectral_rolloff_85, 1.0)
            rolloff_vals.append(1.0 - abs(from_t.spectral_rolloff_85 - to_t.spectral_rolloff_85) / max_r)
        if from_t.spectral_rolloff_95 is not None and to_t.spectral_rolloff_95 is not None:
            max_r = max(from_t.spectral_rolloff_95, to_t.spectral_rolloff_95, 1.0)
            rolloff_vals.append(1.0 - abs(from_t.spectral_rolloff_95 - to_t.spectral_rolloff_95) / max_r)
        if rolloff_vals:
            signals.append(max(0.0, sum(rolloff_vals) / len(rolloff_vals)))
            weights.append(0.15)

        # Spectral slope similarity (10%)
        if from_t.spectral_slope is not None and to_t.spectral_slope is not None:
            max_s = max(abs(from_t.spectral_slope), abs(to_t.spectral_slope), 0.001)
            slope_sim = 1.0 - abs(from_t.spectral_slope - to_t.spectral_slope) / max_s
            signals.append(max(0.0, slope_sim))
            weights.append(0.10)

        # Spectral flux std similarity (5%)
        if from_t.spectral_flux_std is not None and to_t.spectral_flux_std is not None:
            max_f = max(from_t.spectral_flux_std, to_t.spectral_flux_std, 0.001)
            flux_sim = 1.0 - abs(from_t.spectral_flux_std - to_t.spectral_flux_std) / max_f
            signals.append(max(0.0, flux_sim))
            weights.append(0.05)

        if not signals:
            return 0.5

        score = sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)

        # Dissonance penalty: two harsh tracks together = muddy mix
        if (
            from_t.dissonance_mean is not None
            and to_t.dissonance_mean is not None
            and from_t.dissonance_mean > 0.4
            and to_t.dissonance_mean > 0.4
        ):
            score = max(0.0, score - 0.15)

        # Spectral complexity penalty: two complex tracks = clutter
        if (
            from_t.spectral_complexity_mean is not None
            and to_t.spectral_complexity_mean is not None
        ) and abs(from_t.spectral_complexity_mean - to_t.spectral_complexity_mean) > 10:
            score = max(0.0, score - 0.10)

        return score
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestSpectralEnrichment tests/test_services/test_transition_scoring_p2.py::TestDissonancePenalty tests/test_services/test_transition_scoring_p2.py::TestSpectralComplexityPenalty -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich spectral with rolloff, slope, flux_std"
```

---

### Task 7: Enrich Groove scoring component (3 → 6 features)

**Files:**
- Modify: `app/services/transition.py`
- Modify: `tests/test_services/test_transition_scoring_p3.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services/test_transition_scoring_p3.py`:

```python
# ── Groove enrichment ─────────────────────────────────

class TestGrooveEnrichment:
    def test_pulse_clarity_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(pulse_clarity=0.9)
        b = _base(pulse_clarity=0.85)
        score_sim = scorer.score(a, b)

        a_diff = _base(pulse_clarity=0.9)
        b_diff = _base(pulse_clarity=0.2)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_hp_ratio_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(hp_ratio=2.0)
        b = _base(hp_ratio=2.2)
        score_sim = scorer.score(a, b)

        a_diff = _base(hp_ratio=1.0)
        b_diff = _base(hp_ratio=7.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_tempogram_similarity(self) -> None:
        scorer = TransitionScorer()
        vec = [0.8, 0.1, 0.05, 0.05]
        a = _base(tempogram_ratio_vector=vec)
        b = _base(tempogram_ratio_vector=vec)
        score_sim = scorer.score(a, b)

        a_diff = _base(tempogram_ratio_vector=[0.9, 0.05, 0.025, 0.025])
        b_diff = _base(tempogram_ratio_vector=[0.1, 0.5, 0.2, 0.2])
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_none_groove_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(pulse_clarity=None, hp_ratio=None, tempogram_ratio_vector=None)
        b = _base(pulse_clarity=None, hp_ratio=None, tempogram_ratio_vector=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.groove <= 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestGrooveEnrichment -v`
Expected: FAIL

- [ ] **Step 3: Implement groove enrichment**

In `app/services/transition.py`, update `_score_groove`:

```python
    def _score_groove(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        signals: list[float] = []
        weights: list[float] = []

        # Onset rate match (25%)
        if from_t.onset_rate is not None and to_t.onset_rate is not None:
            max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
            signals.append(max(0.0, 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate))
            weights.append(0.25)

        # Kick prominence match (25%)
        if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
            signals.append(max(0.0, 1.0 - abs(from_t.kick_prominence - to_t.kick_prominence)))
            weights.append(0.25)

        # Beat loudness band ratio (20%)
        if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
            beat_cos = self._cosine_similarity(
                from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio
            )
            signals.append(beat_cos)
            weights.append(0.20)

        # Pulse clarity similarity (10%)
        if from_t.pulse_clarity is not None and to_t.pulse_clarity is not None:
            signals.append(max(0.0, 1.0 - abs(from_t.pulse_clarity - to_t.pulse_clarity)))
            weights.append(0.10)

        # HP ratio similarity (10%)
        if from_t.hp_ratio is not None and to_t.hp_ratio is not None:
            max_hp = max(from_t.hp_ratio, to_t.hp_ratio, 1.0)
            signals.append(max(0.0, 1.0 - abs(from_t.hp_ratio - to_t.hp_ratio) / max_hp))
            weights.append(0.10)

        # Tempogram ratio similarity (10%)
        if from_t.tempogram_ratio_vector and to_t.tempogram_ratio_vector:
            tempo_cos = self._cosine_similarity(
                from_t.tempogram_ratio_vector, to_t.tempogram_ratio_vector
            )
            signals.append(tempo_cos)
            weights.append(0.10)

        if not signals:
            return 0.5

        return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestGrooveEnrichment tests/test_services/test_transition_scoring_p2.py::TestBeatLoudnessGroove -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich groove with pulse_clarity, hp_ratio, tempogram"
```

---

### Task 8: Enrich Timbral scoring component (2 → 4 features)

**Files:**
- Modify: `app/services/transition.py`
- Modify: `tests/test_services/test_transition_scoring_p3.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services/test_transition_scoring_p3.py`:

```python
# ── Timbral enrichment ────────────────────────────────

class TestTimbralEnrichment:
    def test_danceability_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                  danceability=1.5)
        b = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                  danceability=1.4)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                       danceability=0.5)
        b_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                       danceability=2.5)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.timbral >= score_diff.timbral

    def test_dynamic_complexity_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                  dynamic_complexity=4.0)
        b = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                  dynamic_complexity=4.2)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                       dynamic_complexity=1.0)
        b_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3,
                       dynamic_complexity=9.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.timbral >= score_diff.timbral

    def test_none_timbral_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(danceability=None, dynamic_complexity=None,
                  spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base(danceability=None, dynamic_complexity=None,
                  spectral_contrast=5.0, pitch_salience_mean=0.3)
        result = scorer.score(a, b)
        assert result.timbral > 0.9  # identical contrast+salience
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_transition_scoring_p3.py::TestTimbralEnrichment -v`
Expected: FAIL

- [ ] **Step 3: Implement timbral enrichment**

In `app/services/transition.py`, update `_score_timbral`:

```python
    def _score_timbral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        """Timbral similarity: spectral contrast + pitch salience + danceability + dynamic complexity."""
        signals: list[float] = []
        weights: list[float] = []

        if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
            diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
            signals.append(max(0.0, 1.0 - diff / 15.0))
            weights.append(0.35)

        if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
            diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
            signals.append(max(0.0, 1.0 - diff / 0.5))
            weights.append(0.35)

        # Danceability similarity (15%)
        if from_t.danceability is not None and to_t.danceability is not None:
            max_d = max(from_t.danceability, to_t.danceability, 0.1)
            signals.append(max(0.0, 1.0 - abs(from_t.danceability - to_t.danceability) / max_d))
            weights.append(0.15)

        # Dynamic complexity similarity (15%)
        if from_t.dynamic_complexity is not None and to_t.dynamic_complexity is not None:
            max_dc = max(from_t.dynamic_complexity, to_t.dynamic_complexity, 0.1)
            signals.append(max(0.0, 1.0 - abs(from_t.dynamic_complexity - to_t.dynamic_complexity) / max_dc))
            weights.append(0.15)

        if not signals:
            return 0.5

        return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
```

- [ ] **Step 4: Run all scoring tests**

Run: `uv run pytest tests/test_services/test_transition.py tests/test_services/test_transition_scoring_p2.py tests/test_services/test_transition_scoring_p3.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transition.py tests/test_services/test_transition_scoring_p3.py
git commit -m "feat(scoring): enrich timbral with danceability and dynamic_complexity"
```

---

### Task 9: Final regression check + lint + typecheck

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: All PASS

- [ ] **Step 2: Run lint**

Run: `uv run ruff check app/core/track_features.py app/services/transition.py app/config.py && uv run ruff format --check app/core/track_features.py app/services/transition.py app/config.py`
Expected: No issues

- [ ] **Step 3: Run typecheck**

Run: `uv run mypy app/core/track_features.py app/services/transition.py`
Expected: Success

- [ ] **Step 4: Fix any issues found, commit if needed**

---

## Phase 2: Classifier & Audit Enrichment

> Separate plan — to be written after Phase 1 is implemented and merged.

## Phase 3: Export Enrichment

> Separate plan — to be written after Phase 1.

## Phase 4: Panel Enrichment

> Separate plan — independent from Phase 1, can be done in parallel.
