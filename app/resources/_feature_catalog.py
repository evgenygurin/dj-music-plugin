"""Static, human-readable metadata for audio-feature and transition-score
columns, used by ``local://sets/{id}/design/data`` to label every value
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
    "track_id": {
        "group": "metadata",
        "label": "Track ID",
        "description": "Primary key / FK to tracks.id.",
    },
    "pipeline_run_id": {
        "group": "metadata",
        "label": "Pipeline run ID",
        "description": "FK to feature_extraction_runs — which analysis pass produced this row.",
    },
    "analysis_level": {
        "group": "metadata",
        "label": "Analysis level",
        "description": "Tier reached: 0 none, 2 L1+L2 (core+librosa), 3 L3 (essentia P1/P2), 5 full local-file re-analysis (L5).",
    },
    "created_at": {
        "group": "metadata",
        "label": "Created at",
        "description": "Timestamp this feature row was first created.",
    },
    "updated_at": {
        "group": "metadata",
        "label": "Updated at",
        "description": "Timestamp this feature row was last updated (e.g. on reanalyze / level upgrade).",
    },
    # ── Tempo ─────────────────────────────────────────────────
    "bpm": {
        "group": "tempo",
        "label": "BPM",
        "description": "Detected tempo in beats per minute (20-300 range). Core signal for transition BPM matching.",
    },
    "bpm_confidence": {
        "group": "tempo",
        "label": "BPM confidence",
        "description": "0-1 confidence in the detected BPM. Mostly NULL on L2 — do not filter on it there.",
    },
    "bpm_stability": {
        "group": "tempo",
        "label": "BPM stability",
        "description": "0-1 measure of how steady the tempo is across the track (outlier-filtered IBI coefficient of variation). Library-wide sits 0.92-0.96 — near-constant, low discriminating power.",
    },
    "variable_tempo": {
        "group": "tempo",
        "label": "Variable tempo flag",
        "description": "True if BPM stability falls below the project threshold — flags tracks with real tempo drift, not stitched-clip artifacts.",
    },
    # ── Loudness ──────────────────────────────────────────────
    "integrated_lufs": {
        "group": "loudness",
        "label": "Integrated LUFS",
        "description": "Whole-track loudness in LUFS (typically -20..-4). Primary signal for transition energy-flow scoring; hard-reject if a pair's gap exceeds 6 LUFS.",
    },
    "short_term_lufs_mean": {
        "group": "loudness",
        "label": "Short-term LUFS (mean)",
        "description": "Average of 3-second-window LUFS measurements across the track.",
    },
    "momentary_max": {
        "group": "loudness",
        "label": "Momentary max loudness",
        "description": "Peak 400ms-window LUFS value — captures the loudest instant, not the average.",
    },
    "rms_dbfs": {
        "group": "loudness",
        "label": "RMS level (dBFS)",
        "description": "Root-mean-square level in dBFS — a simpler, non-perceptual loudness measure alongside LUFS.",
    },
    "true_peak_db": {
        "group": "loudness",
        "label": "True peak (dBFS)",
        "description": "Inter-sample true peak level. Mostly NULL on L2 — do not filter on it there; verify only on L5'd tracks.",
    },
    "crest_factor_db": {
        "group": "loudness",
        "label": "Crest factor (dB)",
        "description": "Peak-to-RMS ratio in dB — how much headroom/dynamics the mix has. Large differences between two tracks penalise the energy transition score.",
    },
    "loudness_range_lu": {
        "group": "loudness",
        "label": "Loudness range (LU)",
        "description": "EBU R128 loudness range — how much the perceived loudness varies over the track. Large differences between two tracks penalise the energy transition score.",
    },
    # ── Energy ────────────────────────────────────────────────
    "energy_mean": {
        "group": "energy",
        "label": "Energy mean",
        "description": "0-1 per-track-normalised energy level (normalised to max=1.0 within the track — NOT a loudness measure; use integrated_lufs for cross-track loudness comparison). Ranks intensity within a slot.",
    },
    "energy_max": {
        "group": "energy",
        "label": "Energy max",
        "description": "Peak per-track-normalised energy value.",
    },
    "energy_std": {
        "group": "energy",
        "label": "Energy std dev",
        "description": "Standard deviation of the energy envelope. Near-constant on this library (low discriminating power).",
    },
    "energy_slope": {
        "group": "energy",
        "label": "Energy slope",
        "description": "Linear trend of the energy envelope over the track — positive means building, negative means winding down. Used for the transition energy-slope-agreement bonus.",
    },
    "energy_sub": {
        "group": "energy",
        "label": "Sub-bass energy (20-60 Hz)",
        "description": "Energy concentrated in the sub-bass band.",
    },
    "energy_low": {
        "group": "energy",
        "label": "Low energy (60-250 Hz)",
        "description": "Energy concentrated in the low/bass band — the classic kick/bass region.",
    },
    "energy_lowmid": {
        "group": "energy",
        "label": "Low-mid energy (250-500 Hz)",
        "description": "Energy concentrated in the low-mid band — 'kick click' region.",
    },
    "energy_mid": {
        "group": "energy",
        "label": "Mid energy",
        "description": "Energy concentrated in the mid band — overlaps vocal formant range.",
    },
    "energy_highmid": {
        "group": "energy",
        "label": "High-mid energy",
        "description": "Energy concentrated in the high-mid band.",
    },
    "energy_high": {
        "group": "energy",
        "label": "High energy",
        "description": "Energy concentrated in the high band — cymbals, hats, air.",
    },
    "energy_sub_ratio": {
        "group": "energy",
        "label": "Sub-bass energy ratio",
        "description": "energy_sub as a fraction of total band energy.",
    },
    "energy_low_ratio": {
        "group": "energy",
        "label": "Low energy ratio",
        "description": "energy_low as a fraction of total band energy.",
    },
    "energy_lowmid_ratio": {
        "group": "energy",
        "label": "Low-mid energy ratio",
        "description": "energy_lowmid as a fraction of total band energy.",
    },
    "energy_mid_ratio": {
        "group": "energy",
        "label": "Mid energy ratio",
        "description": "energy_mid as a fraction of total band energy.",
    },
    "energy_highmid_ratio": {
        "group": "energy",
        "label": "High-mid energy ratio",
        "description": "energy_highmid as a fraction of total band energy.",
    },
    "energy_high_ratio": {
        "group": "energy",
        "label": "High energy ratio",
        "description": "energy_high as a fraction of total band energy.",
    },
    # ── Spectral ──────────────────────────────────────────────
    "spectral_centroid_hz": {
        "group": "spectral",
        "label": "Spectral centroid (Hz)",
        "description": "'Brightness' of the sound — the best spectral discriminator on this library (p10/p90 roughly 1533/2853 Hz). Low values suggest melodic_deep, high values suggest acid.",
    },
    "spectral_rolloff_85": {
        "group": "spectral",
        "label": "Spectral rolloff 85%",
        "description": "Frequency below which 85% of spectral energy is contained.",
    },
    "spectral_rolloff_95": {
        "group": "spectral",
        "label": "Spectral rolloff 95%",
        "description": "Frequency below which 95% of spectral energy is contained.",
    },
    "spectral_flatness": {
        "group": "spectral",
        "label": "Spectral flatness",
        "description": "How noise-like (flat spectrum) vs tonal the sound is.",
    },
    "spectral_flux_mean": {
        "group": "spectral",
        "label": "Spectral flux (mean)",
        "description": "Average frame-to-frame spectral change. Near-constant on this library (low discriminating power).",
    },
    "spectral_flux_std": {
        "group": "spectral",
        "label": "Spectral flux (std dev)",
        "description": "Variability of frame-to-frame spectral change — distinguishes hypnotic (low, repetitive) from breakbeat (high, varied) in theory, but near-constant here.",
    },
    "spectral_slope": {
        "group": "spectral",
        "label": "Spectral slope",
        "description": "Linear slope of the spectrum — tilt toward low or high frequencies.",
    },
    "spectral_contrast": {
        "group": "spectral",
        "label": "Spectral contrast",
        "description": "Peak-to-valley contrast across frequency bands. Near-constant on this library (~3.6 dB, low discriminating power).",
    },
    # ── Key ───────────────────────────────────────────────────
    "key_code": {
        "group": "key",
        "label": "Key code",
        "description": "0-23 index into the Camelot wheel (24 keys). Used for harmonic transition compatibility — see reference://camelot.",
    },
    "key_confidence": {
        "group": "key",
        "label": "Key confidence",
        "description": "0-1 confidence in the detected key. Camelot hard-reject and soft scoring only apply when both tracks in a pair have key_confidence >= 0.5 and are not atonal.",
    },
    "atonality": {
        "group": "key",
        "label": "Atonal flag",
        "description": "True if the track has no reliable tonal center (percussive/noise-dominated). 98.7% of this library is atonal — key distance is a weak/inaudible signal for most pairs here.",
    },
    "hnr_db": {
        "group": "key",
        "label": "Harmonic-to-noise ratio (dB)",
        "description": "How harmonic vs noisy the signal is. Weights the Camelot-distance term in harmonic transition scoring.",
    },
    "chroma_entropy": {
        "group": "key",
        "label": "Chroma entropy",
        "description": "0-1 normalised entropy of the pitch-class (chroma) distribution — how spread out vs concentrated the tonal content is. Near-constant on this library (0.96-0.99, low discriminating power).",
    },
    # ── Rhythm ────────────────────────────────────────────────
    "mfcc_vector": {
        "group": "rhythm",
        "label": "MFCC vector",
        "description": "JSON-encoded 13-coefficient Mel-frequency cepstral vector — a compact timbral 'fingerprint' used for harmonic/timbral similarity scoring.",
    },
    "hp_ratio": {
        "group": "rhythm",
        "label": "Harmonic-percussive ratio",
        "description": "Ratio of harmonic to percussive energy. High values suggest ambient_dub; low values suggest industrial. Drives the adaptive crossfade swap-length choice.",
    },
    "onset_rate": {
        "group": "rhythm",
        "label": "Onset rate (per sec)",
        "description": "How many note/drum onsets occur per second. Near-constant on this library (1.75-2.18, low discriminating power).",
    },
    "pulse_clarity": {
        "group": "rhythm",
        "label": "Pulse clarity",
        "description": "How clear/steady the rhythmic pulse is.",
    },
    "kick_prominence": {
        "group": "rhythm",
        "label": "Kick prominence",
        "description": "0-1 proxy for how dominant the kick drum is in the mix. High values (>0.6) suggest driving/peak-time material; low values suggest minimal. Drives the adaptive kick-kill depth in crossfades.",
    },
    # ── P1 (essentia) ─────────────────────────────────────────
    "danceability": {
        "group": "p1_essentia",
        "label": "Danceability",
        "description": "Essentia DFA danceability score. Unbounded (not 0-1) — compare relatively, not against a fixed scale.",
    },
    "dynamic_complexity": {
        "group": "p1_essentia",
        "label": "Dynamic complexity",
        "description": "Essentia measure of loudness variation complexity, roughly 0-10.",
    },
    "dissonance_mean": {
        "group": "p1_essentia",
        "label": "Dissonance (mean)",
        "description": "0-1 average sensory dissonance. Near-constant on this library (~0.50) — the -0.15 dissonance penalty in scoring rarely discriminates here.",
    },
    "tonnetz_vector": {
        "group": "p1_essentia",
        "label": "Tonnetz vector",
        "description": "JSON-encoded tonal-centroid (Tonnetz) features used for harmonic similarity alongside MFCC.",
    },
    "tempogram_ratio_vector": {
        "group": "p1_essentia",
        "label": "Tempogram ratio vector",
        "description": "JSON-encoded tempogram ratio features — alternate tempo-periodicity representation, depends on beat detection.",
    },
    "beat_loudness_band_ratio": {
        "group": "p1_essentia",
        "label": "Beat-loudness band ratio",
        "description": "Per-band loudness ratio measured at detected beat positions — feeds the 10% beat-loudness term of the drums-stem transition score. Only populated on L5 analyses (fixed 2026-06-23).",
    },
    # ── P2 (essentia) ─────────────────────────────────────────
    "spectral_complexity_mean": {
        "group": "p2_essentia",
        "label": "Spectral complexity (mean)",
        "description": "Essentia measure of the number of prominent spectral peaks — a proxy for arrangement density.",
    },
    "pitch_salience_mean": {
        "group": "p2_essentia",
        "label": "Pitch salience (mean)",
        "description": "0-1 proxy for sustained pitched content (vocals, leads, pads, AND acid TB-303 resonance — not vocal-specific on its own). Combined with spectral_centroid_hz and energy-band distribution to estimate vocal presence.",
    },
    "bpm_histogram_first_peak_weight": {
        "group": "p2_essentia",
        "label": "BPM histogram first-peak weight",
        "description": "Relative weight of the dominant tempo peak in the BPM histogram.",
    },
    "bpm_histogram_second_peak_bpm": {
        "group": "p2_essentia",
        "label": "BPM histogram second-peak BPM",
        "description": "Tempo value of the second-strongest peak in the BPM histogram (e.g. a half/double-time alias).",
    },
    "bpm_histogram_second_peak_weight": {
        "group": "p2_essentia",
        "label": "BPM histogram second-peak weight",
        "description": "Relative weight of the second tempo peak.",
    },
    "phrase_boundaries_ms": {
        "group": "p2_essentia",
        "label": "Phrase boundaries (ms)",
        "description": "JSON-encoded list of detected musical-phrase boundary timestamps.",
    },
    "dominant_phrase_bars": {
        "group": "p2_essentia",
        "label": "Dominant phrase length (bars)",
        "description": "Most common phrase length detected, in bars (typically 8 or 16 for techno).",
    },
    "first_downbeat_ms": {
        "group": "p2_essentia",
        "label": "First downbeat (ms)",
        "description": "Timestamp of the first detected downbeat. Sparse in this library — most rows fall back to 0 (assumes intro starts on the downbeat).",
    },
    # ── Classification / mood ─────────────────────────────────
    "mood": {
        "group": "classification",
        "label": "Mood (subgenre)",
        "description": "Rule-based techno subgenre label (one of 15). Weak signal — median confidence is very low; treat as a hint, not ground truth.",
    },
    "mood_confidence": {
        "group": "classification",
        "label": "Mood confidence",
        "description": "0-1 confidence gap between the winning subgenre score and the runner-up. Low library-wide (~0.05 median).",
    },
    "mood_source": {
        "group": "classification",
        "label": "Mood source",
        "description": "Which pipeline stage produced the mood label (e.g. audio classifier vs Beatport override).",
    },
    "audio_bpm": {
        "group": "classification",
        "label": "Audio-detected BPM (pre-override)",
        "description": "Raw audio-pipeline BPM before any Beatport ground-truth override was applied.",
    },
    "audio_bpm_confidence": {
        "group": "classification",
        "label": "Audio-detected BPM confidence",
        "description": "Confidence of the pre-override audio BPM detection.",
    },
    "audio_key_code": {
        "group": "classification",
        "label": "Audio-detected key code (pre-override)",
        "description": "Raw audio-pipeline key code before any Beatport override.",
    },
    "audio_key_confidence": {
        "group": "classification",
        "label": "Audio-detected key confidence",
        "description": "Confidence of the pre-override audio key detection.",
    },
    "audio_mood": {
        "group": "classification",
        "label": "Audio-detected mood (pre-override)",
        "description": "Raw audio-classifier mood before any override.",
    },
    "audio_mood_confidence": {
        "group": "classification",
        "label": "Audio-detected mood confidence",
        "description": "Confidence of the pre-override audio mood classification.",
    },
    "bpm_source": {
        "group": "classification",
        "label": "BPM source",
        "description": "Which source won for the final ``bpm`` value — e.g. 'audio' or 'beatport'.",
    },
    "key_source": {
        "group": "classification",
        "label": "Key source",
        "description": "Which source won for the final ``key_code`` value — e.g. 'audio' or 'beatport'.",
    },
    # ── Beatport ground truth ─────────────────────────────────
    "beatport_genre": {
        "group": "beatport",
        "label": "Beatport genre",
        "description": "Official Beatport genre label — authoritative but coarser than the project's 15 internal subgenres.",
    },
    "beatport_sub_genre": {
        "group": "beatport",
        "label": "Beatport sub-genre",
        "description": "Official Beatport sub-genre label (e.g. 'Peak Time / Driving', 'Raw / Deep / Hypnotic').",
    },
    "beatport_track_id": {
        "group": "beatport",
        "label": "Beatport track ID",
        "description": "External Beatport catalog ID matched to this track.",
    },
    "beatport_confidence": {
        "group": "beatport",
        "label": "Beatport match confidence",
        "description": "Confidence of the Beatport metadata match (BPM/duration-based matching).",
    },
    "beatport_bpm": {
        "group": "beatport",
        "label": "Beatport BPM",
        "description": "Ground-truth BPM as published on Beatport.",
    },
    "beatport_key": {
        "group": "beatport",
        "label": "Beatport key",
        "description": "Ground-truth musical key as published on Beatport (e.g. 'C Minor').",
    },
    "beatport_camelot": {
        "group": "beatport",
        "label": "Beatport Camelot code",
        "description": "Ground-truth Camelot notation as published on Beatport (e.g. '5A').",
    },
    "beatport_duration_ms": {
        "group": "beatport",
        "label": "Beatport duration (ms)",
        "description": "Ground-truth track duration as published on Beatport, used for match verification.",
    },
    "beatport_isrc": {
        "group": "beatport",
        "label": "Beatport ISRC",
        "description": "International Standard Recording Code from the Beatport catalog entry.",
    },
    "beatport_release": {
        "group": "beatport",
        "label": "Beatport release",
        "description": "Release/album title as published on Beatport.",
    },
    "beatport_label": {
        "group": "beatport",
        "label": "Beatport label",
        "description": "Record label as published on Beatport.",
    },
}


SET_FIELD_CATALOG: dict[str, CatalogEntry] = {
    "id": {
        "group": "identity",
        "label": "Set ID",
        "description": "Primary key of the dj_sets row.",
    },
    "name": {
        "group": "identity",
        "label": "Set name",
        "description": "Human-assigned name for the set.",
    },
    "description": {
        "group": "identity",
        "label": "Set description",
        "description": "Free-text notes about the set (arc summary, quality snapshot, etc.), if any.",
    },
    "target_duration_ms": {
        "group": "target",
        "label": "Target duration (ms)",
        "description": "Desired total playtime for the set, if a fixed duration was requested.",
    },
    "target_bpm_min": {
        "group": "target",
        "label": "Target BPM (min)",
        "description": "Lower bound of the BPM range tracks were selected from.",
    },
    "target_bpm_max": {
        "group": "target",
        "label": "Target BPM (max)",
        "description": "Upper bound of the BPM range tracks were selected from.",
    },
    "target_energy_arc": {
        "group": "target",
        "label": "Target energy arc",
        "description": "JSON-encoded target energy curve used to guide track/section selection, if the set was built against an explicit arc.",
    },
    "template_name": {
        "group": "target",
        "label": "Template name",
        "description": "Set template used to build this set (e.g. roller_90, classic_60) — see reference://templates.",
    },
    "source_playlist_id": {
        "group": "provenance",
        "label": "Source playlist ID",
        "description": "FK to the playlist this set's candidate pool was drawn from, if any.",
    },
    "ym_playlist_id": {
        "group": "provenance",
        "label": "Yandex Music playlist ID",
        "description": "Linked YM playlist ID if this set has been pushed to or synced with Yandex Music.",
    },
}

VERSION_FIELD_CATALOG: dict[str, CatalogEntry] = {
    "id": {
        "group": "identity",
        "label": "Version ID",
        "description": "Primary key of the dj_set_versions row.",
    },
    "set_id": {
        "group": "identity",
        "label": "Parent set ID",
        "description": "FK back to the dj_sets row this version belongs to.",
    },
    "label": {
        "group": "identity",
        "label": "Version label",
        "description": "Human- or generator-assigned label distinguishing this version from siblings (e.g. 'v149', 'ui-rebuild-ga').",
    },
    "generator_run_meta": {
        "group": "provenance",
        "label": "Generator run metadata",
        "description": "JSON metadata describing how this version was produced — algorithm, effective template, transition/key policy.",
    },
    "quality_score": {
        "group": "result",
        "label": "Quality score",
        "description": "0-1 section-aware quality score computed by set_version_build (resolves SectionContext + Neural Mix recipes) — higher is better. Distinct from and usually higher than the raw sequence_optimize fitness score.",
    },
}

ITEM_FIELD_CATALOG: dict[str, CatalogEntry] = {
    "transition_id": {
        "group": "linkage",
        "label": "Transition ID",
        "description": "FK to the persisted Transition row scoring the move into the next track in the set, if one has been persisted.",
    },
    "out_section_id": {
        "group": "linkage",
        "label": "Mix-out section ID",
        "description": "FK to the track_sections row used as this track's mix-out point.",
    },
    "in_section_id": {
        "group": "linkage",
        "label": "Mix-in section ID",
        "description": "FK to the track_sections row used as this track's mix-in point.",
    },
    "mix_in_point_ms": {
        "group": "timing",
        "label": "Mix-in point (ms)",
        "description": "Millisecond offset into this track where the incoming mix begins.",
    },
    "mix_out_point_ms": {
        "group": "timing",
        "label": "Mix-out point (ms)",
        "description": "Millisecond offset into this track where the outgoing mix into the next track begins.",
    },
    "planned_eq": {
        "group": "timing",
        "label": "Planned EQ",
        "description": "JSON-encoded planned EQ automation for this slot, if any.",
    },
    "notes": {
        "group": "identity",
        "label": "Slot notes",
        "description": "Free-text DJ notes attached to this track's slot in the set.",
    },
    "pinned": {
        "group": "identity",
        "label": "Pinned flag",
        "description": "True if this track is pinned in place — the optimizer must not move or remove it.",
    },
}

TRANSITION_FEATURE_CATALOG: dict[str, CatalogEntry] = {
    "id": {
        "group": "metadata",
        "label": "Transition ID",
        "description": "Primary key of the persisted transition row.",
    },
    "from_track_id": {
        "group": "metadata",
        "label": "From track ID",
        "description": "Track being mixed out of.",
    },
    "to_track_id": {
        "group": "metadata",
        "label": "To track ID",
        "description": "Track being mixed into.",
    },
    "from_section_id": {
        "group": "metadata",
        "label": "From section ID",
        "description": "FK to track_sections — the mix-out section on the outgoing track.",
    },
    "to_section_id": {
        "group": "metadata",
        "label": "To section ID",
        "description": "FK to track_sections — the mix-in section on the incoming track.",
    },
    "overlap_ms": {
        "group": "metadata",
        "label": "Overlap (ms)",
        "description": "Duration the two tracks play simultaneously during the transition.",
    },
    "created_at": {
        "group": "metadata",
        "label": "Created at",
        "description": "Timestamp this transition row was first created.",
    },
    "updated_at": {
        "group": "metadata",
        "label": "Updated at",
        "description": "Timestamp this transition row was last updated.",
    },
    "bpm_score": {
        "group": "score",
        "label": "BPM score",
        "description": "0-1 tempo-compatibility component (Gaussian similarity with double/half-time awareness, stability and confidence penalties).",
    },
    "energy_score": {
        "group": "score",
        "label": "Energy score",
        "description": "0-1 LUFS energy-flow component — peaks near a +0.5 LUFS rise into the incoming track, penalised by loudness-range/crest-factor mismatch.",
    },
    "drums_score": {
        "group": "score",
        "label": "Drums (groove) score",
        "description": "0-1 DRUMS-stem component — BPM lock + kick prominence + onset rate + beat-loudness-band similarity. The load-bearing axis for techno peak-time pairs.",
    },
    "bass_score": {
        "group": "score",
        "label": "Bass score",
        "description": "0-1 BASS-stem component — Camelot distance + bass-band energy proximity + BPM. Bass clash is the #1 cause of muddy transitions.",
    },
    "harmonics_score": {
        "group": "score",
        "label": "Harmonics score",
        "description": "0-1 HARMONICS-stem component — Camelot distance weighted by HNR, blended with Tonnetz/MFCC/spectral-contrast similarity.",
    },
    "vocals_score": {
        "group": "score",
        "label": "Vocals score",
        "description": "0-1 VOCALS-stem component — spectral centroid + chroma entropy + pitch salience proximity. A spectral proxy, not real stem separation.",
    },
    "key_distance_weighted": {
        "group": "score",
        "label": "Weighted key distance",
        "description": "Camelot wheel distance between the two tracks, weighted by key reliability (atonality/confidence) — 0 is identical/adjacent-safe, higher is more clash-prone.",
    },
    "low_conflict_score": {
        "group": "score",
        "label": "Low-end conflict score",
        "description": "0-1 measure of bass/sub-bass band overlap risk between the two tracks during the transition window.",
    },
    "overall_quality": {
        "group": "result",
        "label": "Overall quality",
        "description": "0-1 weighted sum of all 6 components (weights depend on the transition intent: MAINTAIN/RAMP_UP/COOL_DOWN/CONTRAST). The number to compare across pairs.",
    },
    "hard_reject": {
        "group": "result",
        "label": "Hard reject flag",
        "description": "True if any hard constraint was violated (BPM diff >10, Camelot distance >=5 with reliable keys, or energy gap >6 LUFS) — overall_quality is forced to 0.0.",
    },
    "reject_reason": {
        "group": "result",
        "label": "Reject reason",
        "description": "Human-readable reason the pair was hard-rejected, or null if not rejected.",
    },
    "transition_bars": {
        "group": "result",
        "label": "Transition length (bars)",
        "description": "Length of the crossfade/blend in bars, scaled by subgenre pair rules.",
    },
    "fx_type": {
        "group": "result",
        "label": "Neural Mix preset",
        "description": "Chosen djay Pro Neural Mix transition preset (e.g. DRUM_SWAP, ECHO_OUT, VOCAL_SUSTAIN) — see docs/transition-scoring.md for the full picker decision tree.",
    },
    "transition_recipe_json": {
        "group": "result",
        "label": "Transition recipe (JSON)",
        "description": "Serialised NeuralMixRecipe — per-stem keyframe levels and FX events that reproduce this transition on djay Pro.",
    },
}


STEM_FEATURE_CATALOG: dict[str, CatalogEntry] = {
    "track_id": {"group": "metadata", "label": "Track ID", "description": "Родительский трек. FK → tracks.id."},
    "stem_name": {"group": "metadata", "label": "Stem", "description": "Тип стема: drums, bass, vocals, other или original."},
    "analysis_level": {"group": "metadata", "label": "Analysis level", "description": "Уровень анализа (6 = L6 полный stem-анализ)."},
    "bpm": {"group": "tempo", "label": "BPM", "description": "Темп стема. Может отличаться от BPM полного трека."},
    "bpm_confidence": {"group": "tempo", "label": "BPM confidence", "description": "Уверенность детекции BPM (0-1)."},
    "bpm_stability": {"group": "tempo", "label": "BPM stability", "description": "Стабильность темпа (0-1). Низкая = переменный темп."},
    "variable_tempo": {"group": "tempo", "label": "Variable tempo", "description": "True если темп значительно меняется."},
    "integrated_lufs": {"group": "loudness", "label": "Integrated LUFS", "description": "Средняя громкость стема по EBU R128. Ключевой параметр для energy budget."},
    "short_term_lufs_mean": {"group": "loudness", "label": "Short-term LUFS mean", "description": "Средняя кратковременная громкость (3s окно)."},
    "momentary_max": {"group": "loudness", "label": "Max momentary LUFS", "description": "Пиковая momentary громкость."},
    "rms_dbfs": {"group": "loudness", "label": "RMS dBFS", "description": "Среднеквадратичная амплитуда в dBFS."},
    "true_peak_db": {"group": "loudness", "label": "True Peak dB", "description": "True peak (intersample). > 0 dBTP = клиппинг."},
    "crest_factor_db": {"group": "loudness", "label": "Crest factor dB", "description": "Пик-фактор. Высокий = динамичный, низкий = сжатый."},
    "loudness_range_lu": {"group": "loudness", "label": "Loudness range LU", "description": "Разброс громкости в LU."},
    "energy_mean": {"group": "energy", "label": "Energy mean", "description": "Средняя энергия стема (нормализованная RMS)."},
    "energy_max": {"group": "energy", "label": "Energy max", "description": "Максимальная энергия."},
    "energy_std": {"group": "energy", "label": "Energy std", "description": "Стандартное отклонение энергии. Низкое = стабильная энергия (лупабельно)."},
    "energy_slope": {"group": "energy", "label": "Energy slope", "description": "Наклон энергии (рост/спад по времени)."},
    "energy_sub": {"group": "energy", "label": "Sub energy (20-60 Hz)", "description": "Энергия в sub-диапазоне. Кик + sub-bass."},
    "energy_low": {"group": "energy", "label": "Low energy (60-250 Hz)", "description": "Энергия в low-диапазоне. Бас и нижняя середина кика."},
    "energy_lowmid": {"group": "energy", "label": "Low-mid energy (250-500 Hz)", "description": "Энергия в low-mid. Теплота, тело звука."},
    "energy_mid": {"group": "energy", "label": "Mid energy (500-2000 Hz)", "description": "Энергия в mid. Основная читаемость, синтезаторы."},
    "energy_highmid": {"group": "energy", "label": "High-mid energy (2-4 kHz)", "description": "Энергия в high-mid. Атака, присутствие, хэты."},
    "energy_high": {"group": "energy", "label": "High energy (4-8 kHz)", "description": "Энергия в high. Воздух, шлейфы, shimmer."},
    "spectral_centroid_hz": {"group": "spectral", "label": "Spectral centroid Hz", "description": "Центр тяжести спектра. Высокий = яркий, низкий = тёмный."},
    "spectral_rolloff_85": {"group": "spectral", "label": "Rolloff 85%", "description": "Частота ниже которой 85% энергии спектра."},
    "spectral_rolloff_95": {"group": "spectral", "label": "Rolloff 95%", "description": "Частота ниже которой 95% энергии спектра."},
    "spectral_contrast": {"group": "spectral", "label": "Spectral contrast", "description": "Контраст пик-провал по октавам."},
    "key_code": {"group": "key", "label": "Key code", "description": "Camelot-код стема (0-23). 0=8B, 23=1B."},
    "key_confidence": {"group": "key", "label": "Key confidence", "description": "Уверенность определения ключа (0-1)."},
    "hnr_db": {"group": "key", "label": "HNR dB", "description": "Harmonics-to-noise ratio. Высокий = гармоничный, низкий = шумный."},
    "chroma_entropy": {"group": "key", "label": "Chroma entropy", "description": "Энтропия хромаграммы. Высокая = много нот, низкая = одна нота/аккорд."},
    "onset_rate": {"group": "rhythm", "label": "Onset rate", "description": "Плотность атак (ударов) в секунду."},
    "pulse_clarity": {"group": "rhythm", "label": "Pulse clarity", "description": "Чёткость пульсации (0-1). Высокая = ровный бит."},
    "kick_prominence": {"group": "rhythm", "label": "Kick prominence", "description": "Выраженность кика (0-1). Высокая = мощный, читаемый кик."},
    "hp_ratio": {"group": "rhythm", "label": "HP ratio", "description": "Доля высокочастотной перкуссии."},
    "danceability": {"group": "danceability", "label": "Danceability", "description": "Танцевальность (0-1)."},
    "dissonance_mean": {"group": "danceability", "label": "Dissonance mean", "description": "Средний диссонанс. >0.3 = резкое, индустриальное звучание."},
    "chords_strength": {"group": "L6", "label": "Chords strength", "description": "Сила аккордовой структуры (Essentia chords)."},
    "chords_changes_rate": {"group": "L6", "label": "Chords changes rate", "description": "Частота смены аккордов."},
    "inharmonicity": {"group": "L6", "label": "Inharmonicity", "description": "Негармоничность спектра. Высокая = колокольность, металличность."},
    "click_detected": {"group": "L6", "label": "Click detected", "description": "Обнаружены ли щелчки/клиппинг в стеме."},
    "saturation_detected": {"group": "L6", "label": "Saturation detected", "description": "Обнаружено ли насыщение/сатурация."},
    "drum_bands": {"group": "L6", "label": "Drum bands", "description": "JSONB: sub_kick, kick_body, snare_clap, hi_hats — энергия и onset_rate per band."},
}
