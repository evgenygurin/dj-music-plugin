# Set Design-Data Dump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new read-only MCP resource `local://sets/{id}/design_data{?version}` that returns one JSON document containing everything the DB knows about a set/version — set fields, version fields, every track's full audio-feature row, every adjacent transition's full score breakdown, and render/beatgrid state — with every leaf value wrapped in a human-readable `{value, label, description}` object instead of a bare number.

**Architecture:** One new static "feature catalog" module holding hand-written `{label, description, group}` metadata for every `TrackAudioFeaturesComputed` column and every `Transition` score column, plus one new resource module that assembles the payload by reusing existing repository methods (`uow.tracks.get_many`, `uow.set_versions.get_latest` / `get_items`, `uow.track_features.filter`, `uow.transitions.get_pairs_batch`, `gather_render_studio`). No new repository methods, no schema changes, no Prefab UI.

**Tech Stack:** Python 3.12, FastMCP v3 `@resource`, SQLAlchemy 2.0 async, pytest + pytest-asyncio, `unittest.mock.MagicMock`/`AsyncMock` for repository mocking (matches the existing pattern in `tests/resources/test_set_cheatsheet_provenance.py` — direct function calls, not the FastMCP `Client`/`seeded_db` fixtures, which are stale Phase-5 xfail stubs).

---

## Task 1: Feature catalog module

**Files:**
- Create: `app/resources/_feature_catalog.py`
- Test: `tests/resources/test_feature_catalog.py`

This module is pure data + one helper function. No DB access, no async.

- [ ] **Step 1: Write the failing test — catalog covers every real column**

```python
# tests/resources/test_feature_catalog.py
from __future__ import annotations

from app.models.transition import Transition
from app.models.track_features import TrackAudioFeaturesComputed
from app.resources._feature_catalog import (
    TRACK_FEATURE_CATALOG,
    TRANSITION_FEATURE_CATALOG,
    describe_field,
)

def test_track_feature_catalog_covers_every_model_column() -> None:
    model_columns = {c.name for c in TrackAudioFeaturesComputed.__table__.columns}
    catalog_columns = set(TRACK_FEATURE_CATALOG.keys())
    missing = model_columns - catalog_columns
    assert not missing, f"missing catalog entries for columns: {sorted(missing)}"

def test_transition_feature_catalog_covers_every_score_column() -> None:
    model_columns = {c.name for c in Transition.__table__.columns}
    catalog_columns = set(TRANSITION_FEATURE_CATALOG.keys())
    missing = model_columns - catalog_columns
    assert not missing, f"missing catalog entries for columns: {sorted(missing)}"

def test_every_catalog_entry_has_group_label_description() -> None:
    for catalog in (TRACK_FEATURE_CATALOG, TRANSITION_FEATURE_CATALOG):
        for name, entry in catalog.items():
            assert entry["group"], f"{name} missing group"
            assert entry["label"], f"{name} missing label"
            assert entry["description"], f"{name} missing description"

def test_describe_field_wraps_value_with_metadata() -> None:
    described = describe_field(TRACK_FEATURE_CATALOG, "bpm", 128.4)
    assert described == {
        "value": 128.4,
        "label": TRACK_FEATURE_CATALOG["bpm"]["label"],
        "description": TRACK_FEATURE_CATALOG["bpm"]["description"],
        "group": TRACK_FEATURE_CATALOG["bpm"]["group"],
    }

def test_describe_field_handles_null_value() -> None:
    described = describe_field(TRACK_FEATURE_CATALOG, "beatport_isrc", None)
    assert described["value"] is None
    assert described["label"] == TRACK_FEATURE_CATALOG["beatport_isrc"]["label"]

def test_describe_field_unknown_column_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        describe_field(TRACK_FEATURE_CATALOG, "not_a_real_column", 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_feature_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.resources._feature_catalog'`

- [ ] **Step 3: Write the catalog module**

```python
# app/resources/_feature_catalog.py
"""Static, human-readable metadata for audio-feature and transition-score
columns, used by ``local://sets/{id}/design_data`` to label every value
instead of returning bare numbers.

This is a hand-written lookup table, not generated at request time — one
entry per column on ``TrackAudioFeaturesComputed`` and ``Transition``.
Descriptions summarise docs/audio-schema.md, docs/audio-pipeline.md,
docs/transition-scoring.md, and docs/domain-glossary.md.
"""

from __future__ import annotations

from typing import Any, TypedDict

class CatalogEntry(TypedDict):
    group: str
    label: str
    description: str

class DescribedField(TypedDict):
    value: Any
    label: str
    description: str
    group: str

def describe_field(catalog: dict[str, CatalogEntry], name: str, value: Any) -> DescribedField:
    """Wrap ``value`` with its catalog metadata. Raises ``KeyError`` if
    ``name`` has no catalog entry — a missing entry is a bug in this
    module, not a runtime condition to swallow."""
    entry = catalog[name]
    return {
        "value": value,
        "label": entry["label"],
        "description": entry["description"],
        "group": entry["group"],
    }

TRACK_FEATURE_CATALOG: dict[str, CatalogEntry] = {
    # ── Metadata ──────────────────────────────────────────────
    "track_id": {"group": "metadata", "label": "Track ID", "description": "Primary key / FK to tracks.id."},
    "pipeline_run_id": {"group": "metadata", "label": "Pipeline run ID", "description": "FK to feature_extraction_runs — which analysis pass produced this row."},
    "analysis_level": {"group": "metadata", "label": "Analysis level", "description": "Tier reached: 0 none, 2 L1+L2 (core+librosa), 3 L3 (essentia P1/P2), 5 full local-file re-analysis (L5)."},
    # ── Tempo ─────────────────────────────────────────────────
    "bpm": {"group": "tempo", "label": "BPM", "description": "Detected tempo in beats per minute (20-300 range). Core signal for transition BPM matching."},
    "bpm_confidence": {"group": "tempo", "label": "BPM confidence", "description": "0-1 confidence in the detected BPM. Mostly NULL on L2 — do not filter on it there."},
    "bpm_stability": {"group": "tempo", "label": "BPM stability", "description": "0-1 measure of how steady the tempo is across the track (outlier-filtered IBI coefficient of variation). Library-wide sits 0.92-0.96 — near-constant, low discriminating power."},
    "variable_tempo": {"group": "tempo", "label": "Variable tempo flag", "description": "True if BPM stability falls below the project threshold — flags tracks with real tempo drift, not stitched-clip artifacts."},
    # ── Loudness ──────────────────────────────────────────────
    "integrated_lufs": {"group": "loudness", "label": "Integrated LUFS", "description": "Whole-track loudness in LUFS (typically -20..-4). Primary signal for transition energy-flow scoring; hard-reject if a pair's gap exceeds 6 LUFS."},
    "short_term_lufs_mean": {"group": "loudness", "label": "Short-term LUFS (mean)", "description": "Average of 3-second-window LUFS measurements across the track."},
    "momentary_max": {"group": "loudness", "label": "Momentary max loudness", "description": "Peak 400ms-window LUFS value — captures the loudest instant, not the average."},
    "rms_dbfs": {"group": "loudness", "label": "RMS level (dBFS)", "description": "Root-mean-square level in dBFS — a simpler, non-perceptual loudness measure alongside LUFS."},
    "true_peak_db": {"group": "loudness", "label": "True peak (dBFS)", "description": "Inter-sample true peak level. Mostly NULL on L2 — do not filter on it there; verify only on L5'd tracks."},
    "crest_factor_db": {"group": "loudness", "label": "Crest factor (dB)", "description": "Peak-to-RMS ratio in dB — how much headroom/dynamics the mix has. Large differences between two tracks penalise the energy transition score."},
    "loudness_range_lu": {"group": "loudness", "label": "Loudness range (LU)", "description": "EBU R128 loudness range — how much the perceived loudness varies over the track. Large differences between two tracks penalise the energy transition score."},
    # ── Energy ────────────────────────────────────────────────
    "energy_mean": {"group": "energy", "label": "Energy mean", "description": "0-1 per-track-normalised energy level (normalised to max=1.0 within the track — NOT a loudness measure; use integrated_lufs for cross-track loudness comparison). Ranks intensity within a slot."},
    "energy_max": {"group": "energy", "label": "Energy max", "description": "Peak per-track-normalised energy value."},
    "energy_std": {"group": "energy", "label": "Energy std dev", "description": "Standard deviation of the energy envelope. Near-constant on this library (low discriminating power)."},
    "energy_slope": {"group": "energy", "label": "Energy slope", "description": "Linear trend of the energy envelope over the track — positive means building, negative means winding down. Used for the transition energy-slope-agreement bonus."},
    "energy_sub": {"group": "energy", "label": "Sub-bass energy (20-60 Hz)", "description": "Energy concentrated in the sub-bass band."},
    "energy_low": {"group": "energy", "label": "Low energy (60-250 Hz)", "description": "Energy concentrated in the low/bass band — the classic kick/bass region."},
    "energy_lowmid": {"group": "energy", "label": "Low-mid energy (250-500 Hz)", "description": "Energy concentrated in the low-mid band — 'kick click' region."},
    "energy_mid": {"group": "energy", "label": "Mid energy", "description": "Energy concentrated in the mid band — overlaps vocal formant range."},
    "energy_highmid": {"group": "energy", "label": "High-mid energy", "description": "Energy concentrated in the high-mid band."},
    "energy_high": {"group": "energy", "label": "High energy", "description": "Energy concentrated in the high band — cymbals, hats, air."},
    "energy_sub_ratio": {"group": "energy", "label": "Sub-bass energy ratio", "description": "energy_sub as a fraction of total band energy."},
    "energy_low_ratio": {"group": "energy", "label": "Low energy ratio", "description": "energy_low as a fraction of total band energy."},
    "energy_lowmid_ratio": {"group": "energy", "label": "Low-mid energy ratio", "description": "energy_lowmid as a fraction of total band energy."},
    "energy_mid_ratio": {"group": "energy", "label": "Mid energy ratio", "description": "energy_mid as a fraction of total band energy."},
    "energy_highmid_ratio": {"group": "energy", "label": "High-mid energy ratio", "description": "energy_highmid as a fraction of total band energy."},
    "energy_high_ratio": {"group": "energy", "label": "High energy ratio", "description": "energy_high as a fraction of total band energy."},
    # ── Spectral ──────────────────────────────────────────────
    "spectral_centroid_hz": {"group": "spectral", "label": "Spectral centroid (Hz)", "description": "'Brightness' of the sound — the best spectral discriminator on this library (p10/p90 roughly 1533/2853 Hz). Low values suggest melodic_deep, high values suggest acid."},
    "spectral_rolloff_85": {"group": "spectral", "label": "Spectral rolloff 85%", "description": "Frequency below which 85% of spectral energy is contained."},
    "spectral_rolloff_95": {"group": "spectral", "label": "Spectral rolloff 95%", "description": "Frequency below which 95% of spectral energy is contained."},
    "spectral_flatness": {"group": "spectral", "label": "Spectral flatness", "description": "How noise-like (flat spectrum) vs tonal the sound is."},
    "spectral_flux_mean": {"group": "spectral", "label": "Spectral flux (mean)", "description": "Average frame-to-frame spectral change. Near-constant on this library (low discriminating power)."},
    "spectral_flux_std": {"group": "spectral", "label": "Spectral flux (std dev)", "description": "Variability of frame-to-frame spectral change — distinguishes hypnotic (low, repetitive) from breakbeat (high, varied) in theory, but near-constant here."},
    "spectral_slope": {"group": "spectral", "label": "Spectral slope", "description": "Linear slope of the spectrum — tilt toward low or high frequencies."},
    "spectral_contrast": {"group": "spectral", "label": "Spectral contrast", "description": "Peak-to-valley contrast across frequency bands. Near-constant on this library (~3.6 dB, low discriminating power)."},
    # ── Key ───────────────────────────────────────────────────
    "key_code": {"group": "key", "label": "Key code", "description": "0-23 index into the Camelot wheel (24 keys). Used for harmonic transition compatibility — see reference://camelot."},
    "key_confidence": {"group": "key", "label": "Key confidence", "description": "0-1 confidence in the detected key. Camelot hard-reject and soft scoring only apply when both tracks in a pair have key_confidence >= 0.5 and are not atonal."},
    "atonality": {"group": "key", "label": "Atonal flag", "description": "True if the track has no reliable tonal center (percussive/noise-dominated). 98.7% of this library is atonal — key distance is a weak/inaudible signal for most pairs here."},
    "hnr_db": {"group": "key", "label": "Harmonic-to-noise ratio (dB)", "description": "How harmonic vs noisy the signal is. Weights the Camelot-distance term in harmonic transition scoring."},
    "chroma_entropy": {"group": "key", "label": "Chroma entropy", "description": "0-1 normalised entropy of the pitch-class (chroma) distribution — how spread out vs concentrated the tonal content is. Near-constant on this library (0.96-0.99, low discriminating power)."},
    # ── Rhythm ────────────────────────────────────────────────
    "mfcc_vector": {"group": "rhythm", "label": "MFCC vector", "description": "JSON-encoded 13-coefficient Mel-frequency cepstral vector — a compact timbral 'fingerprint' used for harmonic/timbral similarity scoring."},
    "hp_ratio": {"group": "rhythm", "label": "Harmonic-percussive ratio", "description": "Ratio of harmonic to percussive energy. High values suggest ambient_dub; low values suggest industrial. Drives the adaptive crossfade swap-length choice."},
    "onset_rate": {"group": "rhythm", "label": "Onset rate (per sec)", "description": "How many note/drum onsets occur per second. Near-constant on this library (1.75-2.18, low discriminating power)."},
    "pulse_clarity": {"group": "rhythm", "label": "Pulse clarity", "description": "How clear/steady the rhythmic pulse is."},
    "kick_prominence": {"group": "rhythm", "label": "Kick prominence", "description": "0-1 proxy for how dominant the kick drum is in the mix. High values (>0.6) suggest driving/peak-time material; low values suggest minimal. Drives the adaptive kick-kill depth in crossfades."},
    # ── P1 (essentia) ─────────────────────────────────────────
    "danceability": {"group": "p1_essentia", "label": "Danceability", "description": "Essentia DFA danceability score. Unbounded (not 0-1) — compare relatively, not against a fixed scale."},
    "dynamic_complexity": {"group": "p1_essentia", "label": "Dynamic complexity", "description": "Essentia measure of loudness variation complexity, roughly 0-10."},
    "dissonance_mean": {"group": "p1_essentia", "label": "Dissonance (mean)", "description": "0-1 average sensory dissonance. Near-constant on this library (~0.50) — the -0.15 dissonance penalty in scoring rarely discriminates here."},
    "tonnetz_vector": {"group": "p1_essentia", "label": "Tonnetz vector", "description": "JSON-encoded tonal-centroid (Tonnetz) features used for harmonic similarity alongside MFCC."},
    "tempogram_ratio_vector": {"group": "p1_essentia", "label": "Tempogram ratio vector", "description": "JSON-encoded tempogram ratio features — alternate tempo-periodicity representation, depends on beat detection."},
    "beat_loudness_band_ratio": {"group": "p1_essentia", "label": "Beat-loudness band ratio", "description": "Per-band loudness ratio measured at detected beat positions — feeds the 10% beat-loudness term of the drums-stem transition score. Only populated on L5 analyses (fixed 2026-06-23)."},
    # ── P2 (essentia) ─────────────────────────────────────────
    "spectral_complexity_mean": {"group": "p2_essentia", "label": "Spectral complexity (mean)", "description": "Essentia measure of the number of prominent spectral peaks — a proxy for arrangement density."},
    "pitch_salience_mean": {"group": "p2_essentia", "label": "Pitch salience (mean)", "description": "0-1 proxy for sustained pitched content (vocals, leads, pads, AND acid TB-303 resonance — not vocal-specific on its own). Combined with spectral_centroid_hz and energy-band distribution to estimate vocal presence."},
    "bpm_histogram_first_peak_weight": {"group": "p2_essentia", "label": "BPM histogram first-peak weight", "description": "Relative weight of the dominant tempo peak in the BPM histogram."},
    "bpm_histogram_second_peak_bpm": {"group": "p2_essentia", "label": "BPM histogram second-peak BPM", "description": "Tempo value of the second-strongest peak in the BPM histogram (e.g. a half/double-time alias)."},
    "bpm_histogram_second_peak_weight": {"group": "p2_essentia", "label": "BPM histogram second-peak weight", "description": "Relative weight of the second tempo peak."},
    "phrase_boundaries_ms": {"group": "p2_essentia", "label": "Phrase boundaries (ms)", "description": "JSON-encoded list of detected musical-phrase boundary timestamps."},
    "dominant_phrase_bars": {"group": "p2_essentia", "label": "Dominant phrase length (bars)", "description": "Most common phrase length detected, in bars (typically 8 or 16 for techno)."},
    "first_downbeat_ms": {"group": "p2_essentia", "label": "First downbeat (ms)", "description": "Timestamp of the first detected downbeat. Sparse in this library — most rows fall back to 0 (assumes intro starts on the downbeat)."},
    # ── Classification / mood ─────────────────────────────────
    "mood": {"group": "classification", "label": "Mood (subgenre)", "description": "Rule-based techno subgenre label (one of 15). Weak signal — median confidence is very low; treat as a hint, not ground truth."},
    "mood_confidence": {"group": "classification", "label": "Mood confidence", "description": "0-1 confidence gap between the winning subgenre score and the runner-up. Low library-wide (~0.05 median)."},
    "mood_source": {"group": "classification", "label": "Mood source", "description": "Which pipeline stage produced the mood label (e.g. audio classifier vs Beatport override)."},
    "audio_bpm": {"group": "classification", "label": "Audio-detected BPM (pre-override)", "description": "Raw audio-pipeline BPM before any Beatport ground-truth override was applied."},
    "audio_bpm_confidence": {"group": "classification", "label": "Audio-detected BPM confidence", "description": "Confidence of the pre-override audio BPM detection."},
    "audio_key_code": {"group": "classification", "label": "Audio-detected key code (pre-override)", "description": "Raw audio-pipeline key code before any Beatport override."},
    "audio_key_confidence": {"group": "classification", "label": "Audio-detected key confidence", "description": "Confidence of the pre-override audio key detection."},
    "audio_mood": {"group": "classification", "label": "Audio-detected mood (pre-override)", "description": "Raw audio-classifier mood before any override."},
    "audio_mood_confidence": {"group": "classification", "label": "Audio-detected mood confidence", "description": "Confidence of the pre-override audio mood classification."},
    "bpm_source": {"group": "classification", "label": "BPM source", "description": "Which source won for the final ``bpm`` value — e.g. 'audio' or 'beatport'."},
    "key_source": {"group": "classification", "label": "Key source", "description": "Which source won for the final ``key_code`` value — e.g. 'audio' or 'beatport'."},
    # ── Beatport ground truth ─────────────────────────────────
    "beatport_genre": {"group": "beatport", "label": "Beatport genre", "description": "Official Beatport genre label — authoritative but coarser than the project's 15 internal subgenres."},
    "beatport_sub_genre": {"group": "beatport", "label": "Beatport sub-genre", "description": "Official Beatport sub-genre label (e.g. 'Peak Time / Driving', 'Raw / Deep / Hypnotic')."},
    "beatport_track_id": {"group": "beatport", "label": "Beatport track ID", "description": "External Beatport catalog ID matched to this track."},
    "beatport_confidence": {"group": "beatport", "label": "Beatport match confidence", "description": "Confidence of the Beatport metadata match (BPM/duration-based matching)."},
    "beatport_bpm": {"group": "beatport", "label": "Beatport BPM", "description": "Ground-truth BPM as published on Beatport."},
    "beatport_key": {"group": "beatport", "label": "Beatport key", "description": "Ground-truth musical key as published on Beatport (e.g. 'C Minor')."},
    "beatport_camelot": {"group": "beatport", "label": "Beatport Camelot code", "description": "Ground-truth Camelot notation as published on Beatport (e.g. '5A')."},
    "beatport_duration_ms": {"group": "beatport", "label": "Beatport duration (ms)", "description": "Ground-truth track duration as published on Beatport, used for match verification."},
    "beatport_isrc": {"group": "beatport", "label": "Beatport ISRC", "description": "International Standard Recording Code from the Beatport catalog entry."},
    "beatport_release": {"group": "beatport", "label": "Beatport release", "description": "Release/album title as published on Beatport."},
    "beatport_label": {"group": "beatport", "label": "Beatport label", "description": "Record label as published on Beatport."},
}

TRANSITION_FEATURE_CATALOG: dict[str, CatalogEntry] = {
    "id": {"group": "metadata", "label": "Transition ID", "description": "Primary key of the persisted transition row."},
    "from_track_id": {"group": "metadata", "label": "From track ID", "description": "Track being mixed out of."},
    "to_track_id": {"group": "metadata", "label": "To track ID", "description": "Track being mixed into."},
    "from_section_id": {"group": "metadata", "label": "From section ID", "description": "FK to track_sections — the mix-out section on the outgoing track."},
    "to_section_id": {"group": "metadata", "label": "To section ID", "description": "FK to track_sections — the mix-in section on the incoming track."},
    "overlap_ms": {"group": "metadata", "label": "Overlap (ms)", "description": "Duration the two tracks play simultaneously during the transition."},
    "bpm_score": {"group": "score", "label": "BPM score", "description": "0-1 tempo-compatibility component (Gaussian similarity with double/half-time awareness, stability and confidence penalties)."},
    "energy_score": {"group": "score", "label": "Energy score", "description": "0-1 LUFS energy-flow component — peaks near a +0.5 LUFS rise into the incoming track, penalised by loudness-range/crest-factor mismatch."},
    "drums_score": {"group": "score", "label": "Drums (groove) score", "description": "0-1 DRUMS-stem component — BPM lock + kick prominence + onset rate + beat-loudness-band similarity. The load-bearing axis for techno peak-time pairs."},
    "bass_score": {"group": "score", "label": "Bass score", "description": "0-1 BASS-stem component — Camelot distance + bass-band energy proximity + BPM. Bass clash is the #1 cause of muddy transitions."},
    "harmonics_score": {"group": "score", "label": "Harmonics score", "description": "0-1 HARMONICS-stem component — Camelot distance weighted by HNR, blended with Tonnetz/MFCC/spectral-contrast similarity."},
    "vocals_score": {"group": "score", "label": "Vocals score", "description": "0-1 VOCALS-stem component — spectral centroid + chroma entropy + pitch salience proximity. A spectral proxy, not real stem separation."},
    "key_distance_weighted": {"group": "score", "label": "Weighted key distance", "description": "Camelot wheel distance between the two tracks, weighted by key reliability (atonality/confidence) — 0 is identical/adjacent-safe, higher is more clash-prone."},
    "low_conflict_score": {"group": "score", "label": "Low-end conflict score", "description": "0-1 measure of bass/sub-bass band overlap risk between the two tracks during the transition window."},
    "overall_quality": {"group": "result", "label": "Overall quality", "description": "0-1 weighted sum of all 6 components (weights depend on the transition intent: MAINTAIN/RAMP_UP/COOL_DOWN/CONTRAST). The number to compare across pairs."},
    "hard_reject": {"group": "result", "label": "Hard reject flag", "description": "True if any hard constraint was violated (BPM diff >10, Camelot distance >=5 with reliable keys, or energy gap >6 LUFS) — overall_quality is forced to 0.0."},
    "reject_reason": {"group": "result", "label": "Reject reason", "description": "Human-readable reason the pair was hard-rejected, or null if not rejected."},
    "transition_bars": {"group": "result", "label": "Transition length (bars)", "description": "Length of the crossfade/blend in bars, scaled by subgenre pair rules."},
    "fx_type": {"group": "result", "label": "Neural Mix preset", "description": "Chosen djay Pro Neural Mix transition preset (e.g. DRUM_SWAP, ECHO_OUT, VOCAL_SUSTAIN) — see docs/transition-scoring.md for the full picker decision tree."},
    "transition_recipe_json": {"group": "result", "label": "Transition recipe (JSON)", "description": "Serialised NeuralMixRecipe — per-stem keyframe levels and FX events that reproduce this transition on djay Pro."},
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_feature_catalog.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/resources/_feature_catalog.py tests/resources/test_feature_catalog.py
git commit -m "feat(resources): add labeled feature catalog for design-data dump"
```

---

## Task 2: Resource skeleton — set + version resolution

**Files:**
- Create: `app/resources/set_design_data.py`
- Test: `tests/resources/test_set_design_data.py`

Mirrors the `_get_latest_version` + `NotFoundError` pattern already used in `app/resources/set.py`, and the direct-function-call + `MagicMock`/`AsyncMock` test pattern already used in `tests/resources/test_set_cheatsheet_provenance.py`.

- [ ] **Step 1: Write the failing test — not-found and set/version block**

```python
# tests/resources/test_set_design_data.py
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.set_design_data import set_design_data
from app.shared.errors import NotFoundError

@pytest.mark.asyncio
async def test_unknown_set_raises_not_found() -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await set_design_data(id=999, uow=uow)

@pytest.mark.asyncio
async def test_set_with_no_versions_raises_not_found() -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100,
            name="Hypnotic Warehouse 130",
            description=None,
            target_duration_ms=5_400_000,
            target_bpm_min=126.0,
            target_bpm_max=132.0,
            target_energy_arc=None,
            template_name="roller_90",
            source_playlist_id=None,
            ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await set_design_data(id=100, uow=uow)

@pytest.mark.asyncio
async def test_set_and_version_blocks_present(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100,
            name="Hypnotic Warehouse 130",
            description="test set",
            target_duration_ms=5_400_000,
            target_bpm_min=126.0,
            target_bpm_max=132.0,
            target_energy_arc=None,
            template_name="roller_90",
            source_playlist_id=None,
            ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(
            id=1000, set_id=100, label="v149", generator_run_meta=None, quality_score=0.79
        )
    )
    uow.set_versions.get_items = AsyncMock(return_value=[])
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(return_value={})
    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[]))
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(
            return_value={
                "version_id": 1000,
                "n_tracks": 0,
                "target_bpm": None,
                "beatgrid": [],
                "job": None,
                "timeline": [],
                "diagnostics": [],
            }
        ),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))

    assert payload["set"]["id"] == 100
    assert payload["set"]["name"] == "Hypnotic Warehouse 130"
    assert payload["version"]["id"] == 1000
    assert payload["version"]["label"] == "v149"
    assert payload["version"]["quality_score"] == 0.79
    assert payload["tracks"] == []
    assert payload["transitions"] == []
    assert payload["render"]["version_id"] == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_set_design_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.resources.set_design_data'`

- [ ] **Step 3: Write the resource skeleton**

```python
# app/resources/set_design_data.py
"""Full labeled data-dump of one set/version, for a design agent building
the next-gen set-building dashboard. Read-only, no mutation, no Prefab UI —
every leaf audio-feature / transition-score value is wrapped with
``{value, label, description, group}`` via ``app.resources._feature_catalog``.

Throwaway-by-design: once the design agent proposes a layout, this
resource's shape is expected to be revisited (folded into ``ui_control_center``,
split into proper resources, or removed). See
docs/superpowers/specs/2026-07-07-set-design-data-dump-design.md.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.repositories.unit_of_work import UnitOfWork
from app.resources._feature_catalog import (
    TRACK_FEATURE_CATALOG,
    TRANSITION_FEATURE_CATALOG,
    describe_field,
)
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.tools.ui.render_studio import gather_render_studio

ANNOTATIONS_READ_ONLY = {"readOnlyHint": True, "idempotentHint": True}
RESOURCE_META = {"version": "1.0.0"}

_SET_FIELDS = (
    "id",
    "name",
    "description",
    "target_duration_ms",
    "target_bpm_min",
    "target_bpm_max",
    "target_energy_arc",
    "template_name",
    "source_playlist_id",
    "ym_playlist_id",
)
_VERSION_FIELDS = ("id", "set_id", "label", "generator_run_meta", "quality_score")

@resource(
    "local://sets/{id}/design_data{?version}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:design_data"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_design_data(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    dj_set = await uow.sets.get(id)
    if dj_set is None:
        raise NotFoundError("set", id)

    if version is not None:
        ver = await uow.set_versions.get(version)
    else:
        ver = await uow.set_versions.get_latest(id)
    if ver is None or getattr(ver, "set_id", None) != id:
        raise NotFoundError("set_version", version or f"latest(set={id})")

    payload: dict[str, Any] = {
        "set": {field: getattr(dj_set, field) for field in _SET_FIELDS},
        "version": {field: getattr(ver, field) for field in _VERSION_FIELDS},
        "tracks": [],
        "transitions": [],
        "render": await gather_render_studio(uow, version_id=ver.id, job_id=None),
    }
    return json.dumps(payload, default=str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_set_design_data.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/resources/set_design_data.py tests/resources/test_set_design_data.py
git commit -m "feat(resources): add set_design_data resource skeleton (set+version blocks)"
```

---

## Task 3: Tracks block — full labeled audio features per track

**Files:**
- Modify: `app/resources/set_design_data.py`
- Modify: `tests/resources/test_set_design_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/resources/test_set_design_data.py`:

```python
@pytest.mark.asyncio
async def test_tracks_block_has_labeled_features(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100,
            name="Hypnotic Warehouse 130",
            description=None,
            target_duration_ms=5_400_000,
            target_bpm_min=126.0,
            target_bpm_max=132.0,
            target_energy_arc=None,
            template_name="roller_90",
            source_playlist_id=None,
            ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(
            id=1000, set_id=100, label="v149", generator_run_meta=None, quality_score=0.79
        )
    )
    uow.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(
                track_id=1,
                sort_index=0,
                transition_id=None,
                out_section_id=None,
                in_section_id=None,
                mix_in_point_ms=0,
                mix_out_point_ms=224_000,
                planned_eq=None,
                notes=None,
                pinned=False,
            )
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(return_value={1: MagicMock(id=1, title="Deconstructive Society")})

    feature_row = MagicMock()
    feature_row.track_id = 1
    for name in TRACK_FEATURE_CATALOG:
        if name == "track_id":
            continue
        setattr(feature_row, name, None)
    feature_row.bpm = 130.0
    feature_row.mood = "hypnotic"

    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[feature_row]))
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(
            return_value={
                "version_id": 1000,
                "n_tracks": 1,
                "target_bpm": 130.0,
                "beatgrid": [],
                "job": None,
                "timeline": [],
                "diagnostics": [],
            }
        ),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))
    tracks = payload["tracks"]

    assert len(tracks) == 1
    track = tracks[0]
    assert track["position"] == 0
    assert track["title"] == "Deconstructive Society"
    assert track["mix_out_point_ms"] == 224_000
    assert track["features"]["bpm"]["value"] == 130.0
    assert track["features"]["bpm"]["label"] == TRACK_FEATURE_CATALOG["bpm"]["label"]
    assert track["features"]["mood"]["value"] == "hypnotic"
```

Add the import at the top of the test file:

```python
from app.resources._feature_catalog import TRACK_FEATURE_CATALOG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_set_design_data.py::test_tracks_block_has_labeled_features -v`
Expected: FAIL with `assert 0 == 1` (tracks list is still empty — hardcoded `[]` from Task 2).

- [ ] **Step 3: Implement the tracks block**

Replace the body of `set_design_data` in `app/resources/set_design_data.py`:

```python
_ITEM_FIELDS = (
    "transition_id",
    "out_section_id",
    "in_section_id",
    "mix_in_point_ms",
    "mix_out_point_ms",
    "planned_eq",
    "notes",
    "pinned",
)

async def _build_tracks_block(uow: UnitOfWork, version_id: int) -> list[dict[str, Any]]:
    items = await uow.set_versions.get_items(version_id)
    if not items:
        return []

    track_ids = [item.track_id for item in items]
    tracks_by_id = await uow.tracks.get_many(track_ids)
    features_page = await uow.track_features.filter(
        where={"track_id__in": track_ids}, limit=max(len(track_ids), 1)
    )
    features_by_track_id = {row.track_id: row for row in features_page.items}

    rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda i: i.sort_index):
        track = tracks_by_id.get(item.track_id)
        feature_row = features_by_track_id.get(item.track_id)
        features: dict[str, Any] = {}
        if feature_row is not None:
            for name in TRACK_FEATURE_CATALOG:
                if not hasattr(feature_row, name):
                    continue
                features[name] = describe_field(
                    TRACK_FEATURE_CATALOG, name, getattr(feature_row, name)
                )
        rows.append(
            {
                "position": item.sort_index,
                "track_id": item.track_id,
                "title": getattr(track, "title", None),
                **{field: getattr(item, field) for field in _ITEM_FIELDS},
                "features": features,
            }
        )
    return rows

@resource(
    "local://sets/{id}/design_data{?version}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:design_data"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_design_data(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    dj_set = await uow.sets.get(id)
    if dj_set is None:
        raise NotFoundError("set", id)

    if version is not None:
        ver = await uow.set_versions.get(version)
    else:
        ver = await uow.set_versions.get_latest(id)
    if ver is None or getattr(ver, "set_id", None) != id:
        raise NotFoundError("set_version", version or f"latest(set={id})")

    payload: dict[str, Any] = {
        "set": {field: getattr(dj_set, field) for field in _SET_FIELDS},
        "version": {field: getattr(ver, field) for field in _VERSION_FIELDS},
        "tracks": await _build_tracks_block(uow, ver.id),
        "transitions": [],
        "render": await gather_render_studio(uow, version_id=ver.id, job_id=None),
    }
    return json.dumps(payload, default=str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_set_design_data.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/resources/set_design_data.py tests/resources/test_set_design_data.py
git commit -m "feat(resources): add labeled tracks+features block to design_data"
```

---

## Task 4: Transitions block — labeled score breakdown per adjacent pair

**Files:**
- Modify: `app/resources/set_design_data.py`
- Modify: `tests/resources/test_set_design_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/resources/test_set_design_data.py`:

```python
@pytest.mark.asyncio
async def test_transitions_block_has_labeled_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.resources._feature_catalog import TRANSITION_FEATURE_CATALOG

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100,
            name="Hypnotic Warehouse 130",
            description=None,
            target_duration_ms=5_400_000,
            target_bpm_min=126.0,
            target_bpm_max=132.0,
            target_energy_arc=None,
            template_name="roller_90",
            source_playlist_id=None,
            ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(
            id=1000, set_id=100, label="v149", generator_run_meta=None, quality_score=0.79
        )
    )
    uow.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(
                track_id=1, sort_index=0, transition_id=None, out_section_id=None,
                in_section_id=None, mix_in_point_ms=0, mix_out_point_ms=224_000,
                planned_eq=None, notes=None, pinned=False,
            ),
            MagicMock(
                track_id=2, sort_index=1, transition_id=None, out_section_id=None,
                in_section_id=None, mix_in_point_ms=0, mix_out_point_ms=240_000,
                planned_eq=None, notes=None, pinned=False,
            ),
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(
        return_value={1: MagicMock(id=1, title="A"), 2: MagicMock(id=2, title="B")}
    )
    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[]))

    transition_row = MagicMock()
    for name in TRANSITION_FEATURE_CATALOG:
        setattr(transition_row, name, None)
    transition_row.from_track_id = 1
    transition_row.to_track_id = 2
    transition_row.overall_quality = 0.87
    transition_row.hard_reject = False
    transition_row.fx_type = "drum_swap"

    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={(1, 2): transition_row})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(
            return_value={
                "version_id": 1000, "n_tracks": 2, "target_bpm": 130.0,
                "beatgrid": [], "job": None, "timeline": [], "diagnostics": [],
            }
        ),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))
    transitions = payload["transitions"]

    assert len(transitions) == 1
    edge = transitions[0]
    assert edge["from_track_id"] == 1
    assert edge["to_track_id"] == 2
    assert edge["scores"]["overall_quality"]["value"] == 0.87
    assert edge["scores"]["overall_quality"]["label"] == TRANSITION_FEATURE_CATALOG["overall_quality"]["label"]
    assert edge["scores"]["fx_type"]["value"] == "drum_swap"

@pytest.mark.asyncio
async def test_transitions_block_missing_pair_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100, name="X", description=None, target_duration_ms=None,
            target_bpm_min=None, target_bpm_max=None, target_energy_arc=None,
            template_name=None, source_playlist_id=None, ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(id=1000, set_id=100, label="v1", generator_run_meta=None, quality_score=0.5)
    )
    uow.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(track_id=1, sort_index=0, transition_id=None, out_section_id=None,
                      in_section_id=None, mix_in_point_ms=0, mix_out_point_ms=0,
                      planned_eq=None, notes=None, pinned=False),
            MagicMock(track_id=2, sort_index=1, transition_id=None, out_section_id=None,
                      in_section_id=None, mix_in_point_ms=0, mix_out_point_ms=0,
                      planned_eq=None, notes=None, pinned=False),
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(return_value={1: MagicMock(id=1, title="A"), 2: MagicMock(id=2, title="B")})
    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[]))
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(return_value={"version_id": 1000, "n_tracks": 2, "target_bpm": None,
                                 "beatgrid": [], "job": None, "timeline": [], "diagnostics": []}),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))
    assert payload["transitions"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_set_design_data.py::test_transitions_block_has_labeled_scores -v`
Expected: FAIL with `assert 0 == 1` (transitions list still hardcoded `[]`).

- [ ] **Step 3: Implement the transitions block**

Add to `app/resources/set_design_data.py` (near `_build_tracks_block`):

```python
async def _build_transitions_block(
    uow: UnitOfWork, sorted_track_ids: list[int]
) -> list[dict[str, Any]]:
    if len(sorted_track_ids) < 2:
        return []

    pairs = list(zip(sorted_track_ids, sorted_track_ids[1:], strict=True))
    transitions_by_pair = await uow.transitions.get_pairs_batch(pairs)

    edges: list[dict[str, Any]] = []
    for from_id, to_id in pairs:
        row = transitions_by_pair.get((from_id, to_id))
        if row is None:
            continue
        scores = {
            name: describe_field(TRANSITION_FEATURE_CATALOG, name, getattr(row, name))
            for name in TRANSITION_FEATURE_CATALOG
            if hasattr(row, name)
        }
        edges.append({"from_track_id": from_id, "to_track_id": to_id, "scores": scores})
    return edges
```

Update `_build_tracks_block` to also return the sort-ordered track id list (needed by the transitions block), and update `set_design_data` to wire it through:

```python
async def _build_tracks_block(
    uow: UnitOfWork, version_id: int
) -> tuple[list[dict[str, Any]], list[int]]:
    items = await uow.set_versions.get_items(version_id)
    if not items:
        return [], []

    sorted_items = sorted(items, key=lambda i: i.sort_index)
    track_ids = [item.track_id for item in sorted_items]
    tracks_by_id = await uow.tracks.get_many(track_ids)
    features_page = await uow.track_features.filter(
        where={"track_id__in": track_ids}, limit=max(len(track_ids), 1)
    )
    features_by_track_id = {row.track_id: row for row in features_page.items}

    rows: list[dict[str, Any]] = []
    for item in sorted_items:
        track = tracks_by_id.get(item.track_id)
        feature_row = features_by_track_id.get(item.track_id)
        features: dict[str, Any] = {}
        if feature_row is not None:
            for name in TRACK_FEATURE_CATALOG:
                if not hasattr(feature_row, name):
                    continue
                features[name] = describe_field(
                    TRACK_FEATURE_CATALOG, name, getattr(feature_row, name)
                )
        rows.append(
            {
                "position": item.sort_index,
                "track_id": item.track_id,
                "title": getattr(track, "title", None),
                **{field: getattr(item, field) for field in _ITEM_FIELDS},
                "features": features,
            }
        )
    return rows, track_ids
```

And in `set_design_data`, replace the tracks/transitions lines:

```python
    tracks, sorted_track_ids = await _build_tracks_block(uow, ver.id)
    payload: dict[str, Any] = {
        "set": {field: getattr(dj_set, field) for field in _SET_FIELDS},
        "version": {field: getattr(ver, field) for field in _VERSION_FIELDS},
        "tracks": tracks,
        "transitions": await _build_transitions_block(uow, sorted_track_ids),
        "render": await gather_render_studio(uow, version_id=ver.id, job_id=None),
    }
    return json.dumps(payload, default=str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_set_design_data.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/resources/set_design_data.py tests/resources/test_set_design_data.py
git commit -m "feat(resources): add labeled transitions block to design_data"
```

---

## Task 5: Register the resource + full-suite check

**Files:**
- Modify: `tests/resources/test_resource_registration.py`
- Modify: `docs/tool-catalog.md`

- [ ] **Step 1: Write the failing test**

Open `tests/resources/test_resource_registration.py`, find the `EXPECTED_TEMPLATE_URIS` frozenset (contains entries like `"local://sets/{id}/cheatsheet{?version}"`), and add the new URI:

```python
    "local://sets/{id}/design_data{?version}",
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_resource_registration.py -v`
Expected: FAIL — `test_expected_uri_inventory_is_consistent` (or equivalent) reports the new URI is expected but not found in source, since `app/resources/set_design_data.py` isn't imported/discovered yet in this test run path. (If the registration test discovers resources purely by scanning `app/resources/*.py` source text rather than importing the FastMCP app, this step may already pass once Task 2's file exists — run it to confirm either way and record the actual result before moving on.)

- [ ] **Step 3: No source change needed if Step 2 already passes; otherwise ensure `app/resources/set_design_data.py` is discoverable**

FastMCP's `FileSystemProvider` auto-discovers every `@resource`-decorated function under `app/resources/` — no manual registration call is required. If the registration test still fails after Task 2-4, the only likely cause is the URI string not matching exactly; diff it byte-for-byte against the `@resource(...)` decorator argument in `app/resources/set_design_data.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_resource_registration.py -v`
Expected: PASS

- [ ] **Step 5: Update the resource count in docs**

In `docs/tool-catalog.md`, under `## Resources (32)`, bump the count to 33 and add a row under `### Local — entity views (16)` (bump that subheading to 17):

```markdown
| `local://sets/{id}/design_data{?version}` | set.py | Full labeled data-dump of one set/version (all track features + transition scores + render state) — design-agent handoff, throwaway pending dashboard redesign |
```

Update the top-line count string `**32 resources**` → `**33 resources**` (search for other occurrences of `27 resources`/`32 resources` in this file's tables and headers and update them consistently — there are two: the `## Resources (32)` heading and the summary line near the top).

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions in `tests/resources/`.

- [ ] **Step 7: Run the full project gate**

Run: `make check`
Expected: lint + typecheck + arch + test all pass. Pay particular attention to `mypy` on `app/resources/set_design_data.py` and `app/resources/_feature_catalog.py` (the `CatalogEntry`/`DescribedField` `TypedDict`s must type-check cleanly) and `import-linter` (this resource only imports `app.repositories`, `app.shared`, `app.server.di`, and `app.tools.ui.render_studio` — confirm that last import doesn't violate the `resources -> tools` dependency direction; if `import-linter` flags it, move `gather_render_studio` render-assembly logic into a shared helper under `app/domain/` or `app/shared/` instead of importing from `app/tools/ui/`, per the dependency rule in docs/architecture.md).

- [ ] **Step 8: Commit**

```bash
git add tests/resources/test_resource_registration.py docs/tool-catalog.md
git commit -m "chore(resources): register design_data resource + doc count"
```

---

## Post-implementation note

This resource is intentionally scoped as a throwaway data-exposure tool for
the design-agent handoff (see spec's "Non-goals / explicit deferrals").
Once the design agent returns a proposed dashboard layout, revisit whether
`set_design_data` becomes a permanent resource, gets folded into
`ui_control_center`, or is deleted — do not treat its current shape as
final architecture.
