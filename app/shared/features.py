"""TrackFeatures dataclass — minimal feature set for transition scoring.

Lives in ``app.shared`` (leaf layer) so both repositories and pure-compute
``app.domain`` modules can import it without crossing layer boundaries.
Repositories must not import from ``app.domain`` (forbidden transitively
by import-linter contract ``v2-server-no-domain`` via the
``app.server → app.repositories`` path), so this DTO must live below the
domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TrackFeatures:
    """Minimal feature set needed for transition scoring."""

    bpm: float | None = None
    key_code: int | None = None
    integrated_lufs: float | None = None
    spectral_centroid_hz: float | None = None
    spectral_flatness: float | None = None
    energy_mean: float | None = None
    onset_rate: float | None = None
    kick_prominence: float | None = None
    hnr_db: float | None = None
    chroma_entropy: float | None = None
    # MFCC vector for spectral similarity
    mfcc_vector: list[float] | None = None
    # Energy bands for balance comparison
    energy_bands: list[float] | None = None

    # P1 features (for scoring integration)
    dissonance_mean: float | None = None
    danceability: float | None = None
    tonnetz_vector: list[float] | None = None
    beat_loudness_band_ratio: list[float] | None = None

    # P2 features
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None
    voicing_ratio: float | None = None

    # Existing but previously unused in scoring
    bpm_stability: float | None = None
    spectral_contrast: float | None = None

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
    # Audit-only (ClippingRiskRule). Not used by the scorer but mapped
    # here so ``run_audit_rules`` can read it from a single feature object.
    true_peak_db: float | None = None

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

    # Beatgrid phase (first downbeat position in ms from track start)
    first_downbeat_ms: float | None = None

    # Mood classification (used by reasoning / filtering, not by TransitionScorer)
    mood: str | None = None
    mood_confidence: float | None = None
    mood_source: str | None = None
    beatport_genre: str | None = None
    beatport_sub_genre: str | None = None
    beatport_confidence: str | None = None
    beatport_bpm: float | None = None
    beatport_key: str | None = None
    beatport_camelot: str | None = None
    audio_bpm: float | None = None
    audio_bpm_confidence: float | None = None
    audio_key_code: int | None = None
    audio_key_confidence: float | None = None
    bpm_source: str | None = None
    key_source: str | None = None

    # Preferred structural anchors selected by the repository.
    phrase_boundaries_ms: list[int] | None = None
    dominant_phrase_bars: int | None = None
    mix_in_section_id: int | None = None
    mix_in_section_type: int | None = None
    mix_in_point_ms: int | None = None
    mix_out_section_id: int | None = None
    mix_out_section_type: int | None = None
    mix_out_point_ms: int | None = None

    # Pipeline tier this row was computed at (0=none, 2=L1+L2, 3=L3, 4=L4, 5=L5).
    # Surfaced via ``local://tracks/{id}/features`` so callers can tell whether
    # P3-tier fields (e.g. ``danceability``, ``tonnetz_vector``) are populated.
    analysis_level: int | None = None

    @classmethod
    def from_db(cls, row: Any) -> TrackFeatures:
        """Construct from a TrackAudioFeaturesComputed DB row."""
        import json

        # Parse mfcc_vector from JSON string if stored
        mfcc = None
        raw_mfcc = getattr(row, "mfcc_vector", None)
        if raw_mfcc:
            mfcc = json.loads(raw_mfcc) if isinstance(raw_mfcc, str) else raw_mfcc

        # Build energy_bands list from individual band columns
        band_fields = (
            "energy_sub",
            "energy_low",
            "energy_lowmid",
            "energy_mid",
            "energy_highmid",
            "energy_high",
        )
        bands_raw = [getattr(row, f, None) for f in band_fields]
        energy_bands: list[float] | None = (
            [float(b) for b in bands_raw if b is not None]
            if all(b is not None for b in bands_raw)
            else None
        )

        # Parse tonnetz_vector from JSON
        tonnetz = None
        raw_tonnetz = getattr(row, "tonnetz_vector", None)
        if raw_tonnetz:
            tonnetz = json.loads(raw_tonnetz) if isinstance(raw_tonnetz, str) else raw_tonnetz

        # Parse beat_loudness_band_ratio from JSON
        beat_loud = None
        raw_beat_loud = getattr(row, "beat_loudness_band_ratio", None)
        if raw_beat_loud:
            beat_loud = (
                json.loads(raw_beat_loud) if isinstance(raw_beat_loud, str) else raw_beat_loud
            )

        # Parse tempogram_ratio_vector from JSON
        tempogram = None
        raw_tempogram = getattr(row, "tempogram_ratio_vector", None)
        if raw_tempogram:
            tempogram = (
                json.loads(raw_tempogram) if isinstance(raw_tempogram, str) else raw_tempogram
            )

        phrase_boundaries = None
        raw_phrase_boundaries = getattr(row, "phrase_boundaries_ms", None)
        if raw_phrase_boundaries:
            phrase_boundaries = (
                json.loads(raw_phrase_boundaries)
                if isinstance(raw_phrase_boundaries, str)
                else raw_phrase_boundaries
            )

        return cls(
            bpm=row.bpm,
            key_code=row.key_code,
            integrated_lufs=row.integrated_lufs,
            spectral_centroid_hz=row.spectral_centroid_hz,
            spectral_flatness=row.spectral_flatness,
            energy_mean=row.energy_mean,
            onset_rate=row.onset_rate,
            kick_prominence=row.kick_prominence,
            hnr_db=row.hnr_db,
            chroma_entropy=row.chroma_entropy,
            mfcc_vector=mfcc,
            energy_bands=energy_bands,
            dissonance_mean=getattr(row, "dissonance_mean", None),
            danceability=getattr(row, "danceability", None),
            tonnetz_vector=tonnetz,
            beat_loudness_band_ratio=beat_loud,
            spectral_complexity_mean=getattr(row, "spectral_complexity_mean", None),
            pitch_salience_mean=getattr(row, "pitch_salience_mean", None),
            voicing_ratio=getattr(row, "voicing_ratio", None),
            bpm_stability=getattr(row, "bpm_stability", None),
            spectral_contrast=getattr(row, "spectral_contrast", None),
            # P3 enrichment: BPM
            bpm_confidence=getattr(row, "bpm_confidence", None),
            variable_tempo=getattr(row, "variable_tempo", None),
            bpm_histogram_first_peak_weight=getattr(row, "bpm_histogram_first_peak_weight", None),
            bpm_histogram_second_peak_bpm=getattr(row, "bpm_histogram_second_peak_bpm", None),
            # P3 enrichment: Harmonic
            atonality=getattr(row, "atonality", None),
            key_confidence=getattr(row, "key_confidence", None),
            # P3 enrichment: Energy
            short_term_lufs_mean=getattr(row, "short_term_lufs_mean", None),
            loudness_range_lu=getattr(row, "loudness_range_lu", None),
            crest_factor_db=getattr(row, "crest_factor_db", None),
            energy_slope=getattr(row, "energy_slope", None),
            true_peak_db=getattr(row, "true_peak_db", None),
            # P3 enrichment: Spectral
            spectral_rolloff_85=getattr(row, "spectral_rolloff_85", None),
            spectral_rolloff_95=getattr(row, "spectral_rolloff_95", None),
            spectral_slope=getattr(row, "spectral_slope", None),
            spectral_flux_std=getattr(row, "spectral_flux_std", None),
            # P3 enrichment: Groove
            pulse_clarity=getattr(row, "pulse_clarity", None),
            hp_ratio=getattr(row, "hp_ratio", None),
            tempogram_ratio_vector=tempogram,
            # P3 enrichment: Timbral
            dynamic_complexity=getattr(row, "dynamic_complexity", None),
            # Mood classification (optional)
            mood=getattr(row, "mood", None),
            mood_confidence=getattr(row, "mood_confidence", None),
            mood_source=getattr(row, "mood_source", None),
            beatport_genre=getattr(row, "beatport_genre", None),
            beatport_sub_genre=getattr(row, "beatport_sub_genre", None),
            beatport_confidence=getattr(row, "beatport_confidence", None),
            beatport_bpm=getattr(row, "beatport_bpm", None),
            beatport_key=getattr(row, "beatport_key", None),
            beatport_camelot=getattr(row, "beatport_camelot", None),
            audio_bpm=getattr(row, "audio_bpm", None),
            audio_bpm_confidence=getattr(row, "audio_bpm_confidence", None),
            audio_key_code=getattr(row, "audio_key_code", None),
            audio_key_confidence=getattr(row, "audio_key_confidence", None),
            bpm_source=getattr(row, "bpm_source", None),
            key_source=getattr(row, "key_source", None),
            phrase_boundaries_ms=phrase_boundaries,
            dominant_phrase_bars=getattr(row, "dominant_phrase_bars", None),
            # Pipeline tier (T-34: was missing → resource showed analysis_level=null
            # for analyzed tracks, hiding which P3 fields are populated).
            analysis_level=getattr(row, "analysis_level", None),
            # Beatgrid phase
            first_downbeat_ms=getattr(row, "first_downbeat_ms", None),
        )
