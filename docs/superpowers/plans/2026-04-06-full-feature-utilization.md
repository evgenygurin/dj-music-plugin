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

### Task 10: Add new features to subgenre profiles

**Files:**
- Modify: `app/audio/classification/profiles.py`
- Modify: `app/models/audio.py` (extend `_CLASSIFIER_FIELDS`)
- Test: `tests/test_audio/test_mood.py`

- [ ] **Step 1: Write failing tests for new profile features**

Add to `tests/test_audio/test_mood.py`:

```python
class TestNewProfileFeatures:
    """Tests that new features influence classification."""

    def test_onset_rate_separates_breakbeat_from_minimal(self) -> None:
        """High onset_rate → breakbeat, low → minimal."""
        classifier = MoodClassifier()
        breakbeat_feats = _ideal_features("breakbeat")
        breakbeat_feats["onset_rate"] = 6.0  # high
        result_bb = classifier.classify(breakbeat_feats)

        minimal_feats = _ideal_features("minimal")
        minimal_feats["onset_rate"] = 2.0  # low
        result_min = classifier.classify(minimal_feats)

        assert result_bb.scores.get("breakbeat", 0) > result_min.scores.get("breakbeat", 0)

    def test_kick_prominence_separates_peak_time_from_ambient(self) -> None:
        classifier = MoodClassifier()
        peak_feats = _ideal_features("peak_time")
        peak_feats["kick_prominence"] = 0.9
        result_peak = classifier.classify(peak_feats)

        ambient_feats = _ideal_features("ambient_dub")
        ambient_feats["kick_prominence"] = 0.1
        result_ambient = classifier.classify(ambient_feats)

        assert result_peak.scores.get("peak_time", 0) > result_ambient.scores.get("peak_time", 0)

    def test_integrated_lufs_separates_hard_from_ambient(self) -> None:
        classifier = MoodClassifier()
        hard_feats = _ideal_features("hard_techno")
        hard_feats["integrated_lufs"] = -6.0
        result_hard = classifier.classify(hard_feats)

        ambient_feats = _ideal_features("ambient_dub")
        ambient_feats["integrated_lufs"] = -16.0
        result_amb = classifier.classify(ambient_feats)

        assert result_hard.scores.get("hard_techno", 0) > result_amb.scores.get("hard_techno", 0)

    def test_spectral_contrast_separates_acid_from_dub(self) -> None:
        classifier = MoodClassifier()
        acid_feats = _ideal_features("acid")
        acid_feats["spectral_contrast"] = 25.0
        result_acid = classifier.classify(acid_feats)

        dub_feats = _ideal_features("dub_techno")
        dub_feats["spectral_contrast"] = 8.0
        result_dub = classifier.classify(dub_feats)

        assert result_acid.scores.get("acid", 0) > result_dub.scores.get("acid", 0)

    def test_bpm_separates_hard_techno_from_breakbeat(self) -> None:
        classifier = MoodClassifier()
        hard_feats = _ideal_features("hard_techno")
        hard_feats["bpm"] = 148.0
        result_hard = classifier.classify(hard_feats)

        bb_feats = _ideal_features("breakbeat")
        bb_feats["bpm"] = 125.0
        result_bb = classifier.classify(bb_feats)

        assert result_hard.scores.get("hard_techno", 0) > result_bb.scores.get("hard_techno", 0)

    def test_classifier_fields_include_new_features(self) -> None:
        from app.models.audio import TrackAudioFeaturesComputed
        fields = TrackAudioFeaturesComputed._CLASSIFIER_FIELDS
        for f in ["onset_rate", "kick_prominence", "integrated_lufs",
                   "spectral_contrast", "spectral_rolloff_85", "bpm",
                   "bpm_histogram_first_peak_weight",
                   "dominant_phrase_bars"]:
            assert f in fields, f"{f} missing from _CLASSIFIER_FIELDS"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_audio/test_mood.py::TestNewProfileFeatures -v`
Expected: FAIL — profiles don't use onset_rate/kick_prominence yet

- [ ] **Step 3: Add missing features to `_CLASSIFIER_FIELDS`**

In `app/models/audio.py`, add to `_CLASSIFIER_FIELDS` tuple (after `spectral_slope`):

```python
        "onset_rate",
        "kick_prominence",
        "integrated_lufs",  # already in tuple? check — if not, add
        "spectral_contrast",
        "spectral_rolloff_85",
        "bpm",  # already in tuple? check
        "bpm_histogram_first_peak_weight",  # already in tuple? check
        "dominant_phrase_bars",
```

Note: some fields may already be in `_CLASSIFIER_FIELDS` — verify before adding duplicates.

- [ ] **Step 4: Add features to subgenre profiles**

In `app/audio/classification/profiles.py`, add to each relevant profile:

**BREAKBEAT profile** — add:
```python
FeatureWeight("onset_rate", weight=2.0, ideal=6.0, tolerance=2.0),
FeatureWeight("kick_prominence", weight=1.0, ideal=0.6, tolerance=0.2),
FeatureWeight("bpm", weight=1.5, ideal=128.0, tolerance=8.0),
```

**MINIMAL profile** — add:
```python
FeatureWeight("onset_rate", weight=1.5, ideal=2.5, tolerance=1.0),
FeatureWeight("kick_prominence", weight=1.0, ideal=0.3, tolerance=0.15),
```

**PEAK_TIME profile** — add:
```python
FeatureWeight("kick_prominence", weight=2.0, ideal=0.85, tolerance=0.1),
FeatureWeight("onset_rate", weight=1.0, ideal=4.5, tolerance=1.5),
```

**INDUSTRIAL profile** — add:
```python
FeatureWeight("kick_prominence", weight=1.5, ideal=0.7, tolerance=0.2),
FeatureWeight("onset_rate", weight=1.0, ideal=5.0, tolerance=2.0),
```

**AMBIENT_DUB profile** — add:
```python
FeatureWeight("kick_prominence", weight=1.0, ideal=0.1, tolerance=0.1),
FeatureWeight("integrated_lufs", weight=1.5, ideal=-16.0, tolerance=3.0),
```

**HARD_TECHNO profile** — add:
```python
FeatureWeight("kick_prominence", weight=1.5, ideal=0.8, tolerance=0.15),
FeatureWeight("integrated_lufs", weight=1.5, ideal=-6.0, tolerance=2.0),
FeatureWeight("bpm", weight=1.5, ideal=145.0, tolerance=5.0),
FeatureWeight("spectral_rolloff_85", weight=1.0, ideal=7000.0, tolerance=2000.0),
```

**ACID profile** — add:
```python
FeatureWeight("spectral_contrast", weight=1.5, ideal=22.0, tolerance=5.0),
```

**DUB_TECHNO profile** — add:
```python
FeatureWeight("spectral_contrast", weight=1.0, ideal=10.0, tolerance=4.0),
FeatureWeight("integrated_lufs", weight=1.0, ideal=-14.0, tolerance=3.0),
```

**TRIBAL profile** — add:
```python
FeatureWeight("onset_rate", weight=1.5, ideal=5.0, tolerance=1.5),
FeatureWeight("bpm_histogram_first_peak_weight", weight=1.5, ideal=0.5, tolerance=0.15),
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_audio/test_mood.py -v`
Expected: All PASS (including existing tests — no regression)

- [ ] **Step 6: Commit**

```bash
git add app/audio/classification/profiles.py app/models/audio.py tests/test_audio/test_mood.py
git commit -m "feat(classifier): add onset_rate, kick_prominence, bpm, lufs, contrast to profiles"
```

---

### Task 11: Add new audit_playlist checks

**Files:**
- Modify: `app/services/curation_service.py`
- Modify: `app/config.py`
- Test: `tests/test_services/test_curation_service.py`

- [ ] **Step 1: Write failing tests for new audit checks**

Add to `tests/test_services/test_curation_service.py`:

```python
class TestAuditNewChecks:
    """Tests for new audio quality checks in audit_playlist."""

    async def test_audit_flags_clipping_risk(self, seeded_db) -> None:
        """true_peak_db > -0.3 → warning."""
        # Create track with true_peak > -0.3
        # Run audit_playlist
        # Assert "clipping risk" in issues
        pass  # TDD: implement after Step 3

    async def test_audit_flags_unreliable_bpm(self, seeded_db) -> None:
        """bpm_confidence < 0.5 → warning."""
        pass

    async def test_audit_flags_variable_tempo(self, seeded_db) -> None:
        """variable_tempo = true → info."""
        pass

    async def test_audit_flags_high_hp_ratio(self, seeded_db) -> None:
        """hp_ratio > 8.0 → warning (too harmonic for techno)."""
        pass

    async def test_audit_flags_noise_spectrum(self, seeded_db) -> None:
        """spectral_flatness > 0.5 → warning."""
        pass
```

- [ ] **Step 2: Add settings for audit thresholds**

In `app/config.py`:

```python
    # ── Audit Thresholds ──────────────────────────────
    audit_true_peak_max: float = -0.3  # dB
    audit_bpm_confidence_min: float = 0.5
    audit_key_confidence_min: float = 0.4
    audit_hp_ratio_max: float = 8.0
    audit_crest_factor_max: float = 30.0  # dB
    audit_spectral_flatness_max: float = 0.5
```

- [ ] **Step 3: Implement new audit checks**

In `app/services/curation_service.py`, in the `audit_playlist` method, add new checks after existing BPM/LUFS checks:

```python
            # New P3 quality checks
            if features.true_peak_db is not None and features.true_peak_db > settings.audit_true_peak_max:
                issues.append({
                    "track_id": track.id,
                    "issue": "clipping_risk",
                    "severity": "warning",
                    "detail": f"True peak {features.true_peak_db:.1f} dB > {settings.audit_true_peak_max} dB",
                })

            if features.bpm_confidence is not None and features.bpm_confidence < settings.audit_bpm_confidence_min:
                issues.append({
                    "track_id": track.id,
                    "issue": "unreliable_bpm",
                    "severity": "warning",
                    "detail": f"BPM confidence {features.bpm_confidence:.2f} < {settings.audit_bpm_confidence_min}",
                })

            if features.key_confidence is not None and features.key_confidence < settings.audit_key_confidence_min:
                issues.append({
                    "track_id": track.id,
                    "issue": "unreliable_key",
                    "severity": "warning",
                    "detail": f"Key confidence {features.key_confidence:.2f} < {settings.audit_key_confidence_min}",
                })

            if features.variable_tempo is True:
                issues.append({
                    "track_id": track.id,
                    "issue": "variable_tempo",
                    "severity": "info",
                    "detail": "Variable tempo — harder to beatmatch",
                })

            if features.hp_ratio is not None and features.hp_ratio > settings.audit_hp_ratio_max:
                issues.append({
                    "track_id": track.id,
                    "issue": "too_harmonic",
                    "severity": "warning",
                    "detail": f"HP ratio {features.hp_ratio:.1f} > {settings.audit_hp_ratio_max} (too harmonic for techno)",
                })

            if features.crest_factor_db is not None and features.crest_factor_db > settings.audit_crest_factor_max:
                issues.append({
                    "track_id": track.id,
                    "issue": "excessive_dynamics",
                    "severity": "warning",
                    "detail": f"Crest factor {features.crest_factor_db:.1f} dB > {settings.audit_crest_factor_max} dB",
                })

            if features.spectral_flatness is not None and features.spectral_flatness > settings.audit_spectral_flatness_max:
                issues.append({
                    "track_id": track.id,
                    "issue": "noise_spectrum",
                    "severity": "warning",
                    "detail": f"Spectral flatness {features.spectral_flatness:.2f} > {settings.audit_spectral_flatness_max}",
                })
```

- [ ] **Step 4: Flesh out test implementations and run**

Run: `uv run pytest tests/test_services/test_curation_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/curation_service.py app/config.py tests/test_services/test_curation_service.py
git commit -m "feat(audit): add 7 new quality checks for P3 features"
```

---

### Task 12: Add review_set_quality enrichments

**Files:**
- Modify: `app/services/curation_service.py`
- Test: `tests/test_services/test_curation_service.py`

- [ ] **Step 1: Write failing test**

```python
class TestReviewSetQualityEnrichment:
    async def test_review_includes_danceability_arc(self, seeded_db) -> None:
        """review_set_quality should report danceability monotonicity."""
        pass  # implement with seeded set

    async def test_review_flags_hp_ratio_jumps(self, seeded_db) -> None:
        """Large hp_ratio jumps between consecutive tracks → warning."""
        pass

    async def test_review_flags_phrase_mismatch(self, seeded_db) -> None:
        """Different dominant_phrase_bars between neighbors → warning."""
        pass
```

- [ ] **Step 2: Implement review enrichments**

In `review_set_quality`, after existing BPM/energy analysis, add:

```python
            # Danceability arc analysis
            danceability_values = [f.danceability for f in features_list if f.danceability is not None]
            if danceability_values:
                result["danceability_arc"] = {
                    "min": min(danceability_values),
                    "max": max(danceability_values),
                    "mean": sum(danceability_values) / len(danceability_values),
                }

            # HP ratio jump detection
            hp_jumps = []
            for i in range(len(features_list) - 1):
                f_a, f_b = features_list[i], features_list[i + 1]
                if f_a.hp_ratio is not None and f_b.hp_ratio is not None:
                    jump = abs(f_a.hp_ratio - f_b.hp_ratio)
                    if jump > 2.0:
                        hp_jumps.append({"position": i + 1, "jump": round(jump, 2)})
            if hp_jumps:
                result["hp_ratio_jumps"] = hp_jumps

            # Phrase alignment check
            phrase_mismatches = []
            for i in range(len(features_list) - 1):
                f_a, f_b = features_list[i], features_list[i + 1]
                if f_a.dominant_phrase_bars is not None and f_b.dominant_phrase_bars is not None:
                    if f_a.dominant_phrase_bars != f_b.dominant_phrase_bars:
                        phrase_mismatches.append({
                            "position": i + 1,
                            "bars_a": f_a.dominant_phrase_bars,
                            "bars_b": f_b.dominant_phrase_bars,
                        })
            if phrase_mismatches:
                result["phrase_mismatches"] = phrase_mismatches
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_services/test_curation_service.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/curation_service.py tests/test_services/test_curation_service.py
git commit -m "feat(review): add danceability arc, HP ratio jumps, phrase alignment checks"
```

---

## Phase 3: Export Enrichment

### Task 13: Extend M3U8 with new EXTDJ tags

**Files:**
- Modify: `app/services/export.py`
- Test: `tests/test_services/test_export.py`

- [ ] **Step 1: Write failing tests for new M3U8 tags**

Add to `tests/test_services/test_export.py`:

```python
def test_m3u8_includes_new_p3_tags(sample_data: SetExportData, tmp_path: Path) -> None:
    """M3U8 should include mood_confidence, rms, peak, crest, danceability, hp_ratio, phrase."""
    # Update sample_data tracks with new fields
    sample_data.tracks[0].mood_confidence = 0.85
    sample_data.tracks[0].rms_dbfs = -12.5
    sample_data.tracks[0].true_peak_db = -0.8
    sample_data.tracks[0].crest_factor_db = 11.0
    sample_data.tracks[0].danceability = 1.5
    sample_data.tracks[0].hp_ratio = 2.3
    sample_data.tracks[0].dominant_phrase_bars = 8

    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()

    assert "#EXTDJ-MOOD-CONFIDENCE:0.85" in content
    assert "#EXTDJ-RMS:-12.5" in content
    assert "#EXTDJ-PEAK:-0.8" in content
    assert "#EXTDJ-CREST:11.0" in content
    assert "#EXTDJ-DANCEABILITY:1.50" in content
    assert "#EXTDJ-HP-RATIO:2.30" in content
    assert "#EXTDJ-PHRASE:8 bars" in content
```

- [ ] **Step 2: Add new fields to ExportTrack dataclass**

In `app/services/export.py`, extend `ExportTrack`:

```python
    # P3 enrichment fields
    mood_confidence: float | None = None
    rms_dbfs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    danceability: float | None = None
    hp_ratio: float | None = None
    dominant_phrase_bars: int | None = None
    variable_tempo: bool | None = None
```

- [ ] **Step 3: Add new EXTDJ tags to M3U8 writer**

In `write_m3u8`, after existing EXTDJ tags per-track, add:

```python
                if track.mood_confidence is not None:
                    lines.append(f"#EXTDJ-MOOD-CONFIDENCE:{track.mood_confidence:.2f}")
                if track.rms_dbfs is not None:
                    lines.append(f"#EXTDJ-RMS:{track.rms_dbfs:.1f}")
                if track.true_peak_db is not None:
                    lines.append(f"#EXTDJ-PEAK:{track.true_peak_db:.1f}")
                if track.crest_factor_db is not None:
                    lines.append(f"#EXTDJ-CREST:{track.crest_factor_db:.1f}")
                if track.danceability is not None:
                    lines.append(f"#EXTDJ-DANCEABILITY:{track.danceability:.2f}")
                if track.hp_ratio is not None:
                    lines.append(f"#EXTDJ-HP-RATIO:{track.hp_ratio:.2f}")
                if track.dominant_phrase_bars is not None:
                    lines.append(f"#EXTDJ-PHRASE:{track.dominant_phrase_bars} bars")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_export.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/export.py tests/test_services/test_export.py
git commit -m "feat(export): add 7 new EXTDJ M3U8 tags for P3 features"
```

---

### Task 14: Extend JSON guide with full features

**Files:**
- Modify: `app/services/export.py`
- Modify: `app/services/delivery_service.py`
- Test: `tests/test_services/test_export.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_services/test_export.py`:

```python
def test_json_guide_includes_full_audio_features(sample_data: SetExportData, tmp_path: Path) -> None:
    """JSON guide should include all audio features per track."""
    sample_data.tracks[0].audio_features = {
        "tempo": {"bpm": 128.0, "confidence": 0.98, "stability": 0.95, "variable_tempo": False},
        "loudness": {"integrated_lufs": -8.0, "short_term_mean": -9.5, "rms_dbfs": -12.0,
                      "true_peak_db": -0.8, "crest_factor_db": 11.0, "loudness_range_lu": 8.0},
        "energy": {"mean": 0.6, "max": 1.0},
        "classification": {"mood": "driving", "confidence": 0.85},
    }
    path = write_json_guide(sample_data, tmp_path / "guide.json")
    import json
    data = json.loads(path.read_text())
    track = data["tracks"][0]
    assert "audio_features" in track
    assert track["audio_features"]["tempo"]["bpm"] == 128.0
    assert track["audio_features"]["loudness"]["true_peak_db"] == -0.8
```

- [ ] **Step 2: Add `audio_features` dict to ExportTrack**

```python
    audio_features: dict[str, Any] | None = None  # full features for JSON guide
```

- [ ] **Step 3: Update JSON guide writer to include audio_features**

In `write_json_guide`, extend track dict:

```python
                if track.audio_features:
                    track_dict["audio_features"] = track.audio_features
```

- [ ] **Step 4: Update delivery_service to populate audio_features**

In `build_export_data`, when building ExportTrack, add full features dict from DB row.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_services/test_export.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/export.py app/services/delivery_service.py tests/test_services/test_export.py
git commit -m "feat(export): add full audio_features dict to JSON guide"
```

---

### Task 15: Extend cheat sheet with phrase/flags

**Files:**
- Modify: `app/services/export.py`
- Test: `tests/test_services/test_export.py`

- [ ] **Step 1: Write failing test**

```python
def test_cheat_sheet_includes_phrase_and_flags(sample_data: SetExportData, tmp_path: Path) -> None:
    sample_data.tracks[0].dominant_phrase_bars = 8
    sample_data.tracks[0].variable_tempo = True
    sample_data.tracks[0].true_peak_db = -0.1
    sample_data.tracks[0].mood_confidence = 0.3

    path = write_cheat_sheet(sample_data, tmp_path / "cheat.txt")
    content = path.read_text()

    assert "8 bars" in content
    assert "VarTempo" in content or "Variable" in content
```

- [ ] **Step 2: Update cheat sheet writer**

Add Phrase column and flags to per-track output:

```python
            # Build flags
            flags = []
            if track.variable_tempo:
                flags.append("⚠ VarTempo")
            if track.true_peak_db is not None and track.true_peak_db > -0.5:
                flags.append("⚠ Peak>{:.1f}".format(track.true_peak_db))
            if track.mood_confidence is not None and track.mood_confidence < 0.5:
                flags.append("⚠ LowConf")

            phrase_str = f"{track.dominant_phrase_bars} bars" if track.dominant_phrase_bars else ""
            flag_str = "  ".join(flags)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_services/test_export.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/export.py tests/test_services/test_export.py
git commit -m "feat(export): add phrase bars and warning flags to cheat sheet"
```

---

## Phase 4: Panel Enrichment

### Task 16: Add new dashboard distribution charts

**Files:**
- Modify: `panel/lib/queries/dashboard.ts`
- Create: `panel/components/charts/danceability-distribution.tsx`
- Create: `panel/components/charts/hp-ratio-distribution.tsx`
- Create: `panel/components/charts/phrase-distribution.tsx`
- Modify: `panel/app/page.tsx`

- [ ] **Step 1: Add new query functions**

In `panel/lib/queries/dashboard.ts`:

```typescript
export interface DanceabilityBin {
  bin: number;
  count: number;
}

export async function getDanceabilityDistribution(): Promise<DanceabilityBin[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("track_audio_features_computed")
    .select("danceability")
    .not("danceability", "is", null);

  if (!data) return [];
  const bins: Record<number, number> = {};
  for (const row of data) {
    const bin = Math.round(row.danceability * 2) / 2; // 0.5 step bins
    bins[bin] = (bins[bin] || 0) + 1;
  }
  return Object.entries(bins)
    .map(([bin, count]) => ({ bin: Number(bin), count }))
    .sort((a, b) => a.bin - b.bin);
}

export interface HpRatioBin {
  bin: number;
  count: number;
}

export async function getHpRatioDistribution(): Promise<HpRatioBin[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("track_audio_features_computed")
    .select("hp_ratio")
    .not("hp_ratio", "is", null);

  if (!data) return [];
  const bins: Record<number, number> = {};
  for (const row of data) {
    const bin = Math.round(row.hp_ratio); // integer bins
    bins[bin] = (bins[bin] || 0) + 1;
  }
  return Object.entries(bins)
    .map(([bin, count]) => ({ bin: Number(bin), count }))
    .sort((a, b) => a.bin - b.bin);
}

export interface PhraseCount {
  bars: number;
  count: number;
}

export async function getPhraseDistribution(): Promise<PhraseCount[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("track_audio_features_computed")
    .select("dominant_phrase_bars")
    .not("dominant_phrase_bars", "is", null);

  if (!data) return [];
  const groups: Record<number, number> = {};
  for (const row of data) {
    const bars = row.dominant_phrase_bars;
    groups[bars] = (groups[bars] || 0) + 1;
  }
  return Object.entries(groups)
    .map(([bars, count]) => ({ bars: Number(bars), count }))
    .sort((a, b) => a.bars - b.bars);
}

export interface QualityFlags {
  variable_tempo_count: number;
  atonality_count: number;
  avg_bpm_confidence: number;
}

export async function getQualityFlags(): Promise<QualityFlags> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("track_audio_features_computed")
    .select("variable_tempo, atonality, bpm_confidence");

  if (!data) return { variable_tempo_count: 0, atonality_count: 0, avg_bpm_confidence: 0 };

  const vt = data.filter((r) => r.variable_tempo === true).length;
  const at = data.filter((r) => r.atonality === true).length;
  const confs = data.filter((r) => r.bpm_confidence != null).map((r) => r.bpm_confidence);
  const avgConf = confs.length > 0 ? confs.reduce((a, b) => a + b, 0) / confs.length : 0;

  return { variable_tempo_count: vt, atonality_count: at, avg_bpm_confidence: avgConf };
}
```

- [ ] **Step 2: Create chart components**

Create `panel/components/charts/danceability-distribution.tsx`, `hp-ratio-distribution.tsx`, `phrase-distribution.tsx` following the existing pattern from `bpm-distribution.tsx` (BarChart with neon gradient).

- [ ] **Step 3: Add charts to dashboard page**

In `panel/app/page.tsx`, add queries to `Promise.all` and render new chart row below existing charts.

- [ ] **Step 4: Verify in browser**

Run: `cd panel && bun dev` → http://localhost:3000
Expected: New charts visible on dashboard

- [ ] **Step 5: Commit**

```bash
git add panel/lib/queries/dashboard.ts panel/components/charts/ panel/app/page.tsx
git commit -m "feat(panel): add danceability, HP ratio, phrase distribution charts to dashboard"
```

---

### Task 17: Add optional columns to track list table

**Files:**
- Modify: `panel/app/library/library-table.tsx`
- Modify: `panel/lib/queries/tracks.ts`

- [ ] **Step 1: Extend track list query with new fields**

In `panel/lib/queries/tracks.ts`, add to the SELECT in `getTrackList`:

```typescript
// Add to feature fields
energy_mean, hp_ratio, danceability, dynamic_complexity, mood_confidence, analysis_level
```

- [ ] **Step 2: Add toggle-able columns to table**

In `panel/app/library/library-table.tsx`, add optional columns (hidden by default) using TanStack Table `columnVisibility`:

```typescript
{
  accessorKey: "hp_ratio",
  header: "HP Ratio",
  cell: ({ row }) => row.original.hp_ratio?.toFixed(2) ?? "—",
  enableHiding: true,
},
{
  accessorKey: "danceability",
  header: "Dance",
  cell: ({ row }) => row.original.danceability?.toFixed(2) ?? "—",
  enableHiding: true,
},
{
  accessorKey: "mood_confidence",
  header: "Conf",
  cell: ({ row }) => row.original.mood_confidence != null
    ? `${(row.original.mood_confidence * 100).toFixed(0)}%`
    : "—",
  enableHiding: true,
},
```

Add column visibility dropdown (shadcn DropdownMenu).

- [ ] **Step 3: Verify in browser**

Expected: Column toggle dropdown visible, optional columns work

- [ ] **Step 4: Commit**

```bash
git add panel/app/library/library-table.tsx panel/lib/queries/tracks.ts
git commit -m "feat(panel): add optional hp_ratio, danceability, mood_confidence columns to track list"
```

---

### Task 18: Final regression + lint across all phases

- [ ] **Step 1: Run full Python test suite**

Run: `uv run pytest tests/ -v --timeout=120`
Expected: All PASS

- [ ] **Step 2: Run lint + typecheck**

Run: `make check`
Expected: No issues

- [ ] **Step 3: Build panel**

Run: `cd panel && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit any fixes**
