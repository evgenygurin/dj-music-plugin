"""Audio feature DTOs."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrackFeaturesView(BaseModel):
    """Audio features view — full surface over the persisted columns.

    Audit iter 40 (T-38): the prior View exposed 11 of the 47+ columns
    on ``track_audio_features_computed``. None of the P1/P2 enrichment
    fields (``danceability``, ``dissonance_mean``, ``tonnetz_vector``,
    ``spectral_complexity_mean``, …) and none of the loudness /
    spectral / energy-band columns were projectable through
    ``entity_get(track_features, id, fields=[...])``. The pipeline writes
    them, the scorer reads them, but tooling was blind to them.

    Fields are kept ``None``-default so older rows that haven't been
    re-analysed at the higher tiers still validate cleanly.
    """

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    analysis_level: int = 0

    # Tempo (4)
    bpm: float | None = None
    bpm_confidence: float | None = None
    bpm_stability: float | None = None
    variable_tempo: bool | None = None

    # Loudness (7)
    integrated_lufs: float | None = None
    short_term_lufs_mean: float | None = None
    momentary_max: float | None = None
    rms_dbfs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    loudness_range_lu: float | None = None

    # Energy — scalars + 6 band absolutes + 6 band ratios (16)
    energy_mean: float | None = None
    energy_max: float | None = None
    energy_std: float | None = None
    energy_slope: float | None = None
    energy_sub: float | None = None
    energy_low: float | None = None
    energy_lowmid: float | None = None
    energy_mid: float | None = None
    energy_highmid: float | None = None
    energy_high: float | None = None
    energy_sub_ratio: float | None = None
    energy_low_ratio: float | None = None
    energy_lowmid_ratio: float | None = None
    energy_mid_ratio: float | None = None
    energy_highmid_ratio: float | None = None
    energy_high_ratio: float | None = None

    # Spectral (8)
    spectral_centroid_hz: float | None = None
    spectral_rolloff_85: float | None = None
    spectral_rolloff_95: float | None = None
    spectral_flatness: float | None = None
    spectral_flux_mean: float | None = None
    spectral_flux_std: float | None = None
    spectral_slope: float | None = None
    spectral_contrast: float | None = None

    # Key / harmonic (5)
    key_code: int | None = None
    camelot: str | None = None
    key_confidence: float | None = None
    atonality: bool | None = None
    hnr_db: float | None = None
    chroma_entropy: float | None = None

    # Rhythm (5)
    # ``mfcc_vector`` is stored as JSON-encoded string; expose raw so
    # callers can ``json.loads`` if they want the 13-coefficient vector.
    mfcc_vector: str | None = None
    hp_ratio: float | None = None
    onset_rate: float | None = None
    pulse_clarity: float | None = None
    kick_prominence: float | None = None

    # P1 enrichment (6) — vectors as JSON strings, scalars typed
    danceability: float | None = None
    dynamic_complexity: float | None = None
    dissonance_mean: float | None = None
    tonnetz_vector: str | None = None
    tempogram_ratio_vector: str | None = None
    beat_loudness_band_ratio: str | None = None

    # P2 enrichment (6, ``phrase_boundaries_ms`` is too large to default-emit
    # but available via explicit ``fields=...``)
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None
    bpm_histogram_first_peak_weight: float | None = None
    bpm_histogram_second_peak_bpm: float | None = None
    bpm_histogram_second_peak_weight: float | None = None
    dominant_phrase_bars: int | None = None
    phrase_boundaries_ms: str | None = None

    # Beatgrid phase
    first_downbeat_ms: float | None = None

    # Mood classification
    mood: str | None = None
    mood_confidence: float | None = None
    mood_source: str | None = None

    # Original audio-analysis values retained after provider canonicalization.
    audio_bpm: float | None = None
    audio_bpm_confidence: float | None = None
    audio_key_code: int | None = None
    audio_key_confidence: float | None = None
    audio_mood: str | None = None
    audio_mood_confidence: float | None = None
    bpm_source: str | None = None
    key_source: str | None = None

    # Beatport ground-truth metadata (matched + BPM/duration-verified)
    beatport_genre: str | None = None
    beatport_sub_genre: str | None = None
    beatport_track_id: int | None = None
    beatport_confidence: str | None = None
    beatport_bpm: float | None = None
    beatport_key: str | None = None
    beatport_camelot: str | None = None
    beatport_duration_ms: int | None = None
    beatport_isrc: str | None = None
    beatport_release: str | None = None
    beatport_label: str | None = None

    @model_validator(mode="after")
    def _derive_camelot(self) -> Self:
        if self.camelot is not None:
            return self
        if self.beatport_camelot:
            self.camelot = self.beatport_camelot
            return self
        if self.key_code is None:
            return self
        from app.domain.camelot.wheel import key_code_to_camelot

        try:
            self.camelot = key_code_to_camelot(int(self.key_code))
        except ValueError:
            self.camelot = None
        return self


class TrackFeaturesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    analysis_level__eq: int | None = None
    analysis_level__gte: int | None = None
    analysis_level__lt: int | None = None
    bpm__eq: float | None = None
    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__range: list[float] | None = None
    # key_code: full lookup family. Audit iter 6 caught ``key_code__in``
    # rejected even though every harmonic compatibility query
    # ("tracks in 8A or 8B") needs it.
    key_code__eq: int | None = None
    key_code__in: list[int] | None = None
    key_code__range: list[int] | None = None
    key_code__isnull: bool | None = None
    # integrated_lufs: range/gte/lte for loudness-bucket queries.
    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None
    integrated_lufs__range: list[float] | None = None
    mood__eq: str | None = None
    mood__in: list[str] | None = None
    mood__isnull: bool | None = None
    # Beatport ground-truth genre — the authoritative subgenre filter.
    beatport_genre__eq: str | None = None
    beatport_genre__in: list[str] | None = None
    beatport_genre__icontains: str | None = None
    beatport_genre__isnull: bool | None = None
    beatport_confidence__eq: str | None = None
    bpm_source__eq: str | None = None
    key_source__eq: str | None = None
    mood_source__eq: str | None = None
    # Confidence + scalar feature lookups (audit iter 25). The most
    # common analytics query is "filter by mood_confidence >= 0.1
    # to exclude low-quality classifications".
    mood_confidence__gte: float | None = None
    mood_confidence__lte: float | None = None
    energy_mean__gte: float | None = None
    energy_mean__lte: float | None = None
    spectral_centroid_hz__gte: float | None = None
    spectral_centroid_hz__lte: float | None = None
    hp_ratio__gte: float | None = None
    hp_ratio__lte: float | None = None
    kick_prominence__gte: float | None = None
    kick_prominence__lte: float | None = None
    # Audit iter 40: scalar P1/P2/loudness fields lacking lookups.
    # ``true_peak_db`` is the canonical clipping-audit query
    # ("find tracks above 0 dBTP"); ``key_confidence`` filters out
    # tracks with an unreliable detected key; ``atonality`` and
    # ``variable_tempo`` are the boolean discriminators.
    # ``__isnull`` on the NULL-heavy essentia / L3+ columns is THE
    # "which tracks still need analysis" lookup — ``__gte``/``__lte``
    # silently drop NULL rows (probe 2026-07-03; see rules/tools.md
    # "L2 feature columns that are mostly NULL").
    true_peak_db__gte: float | None = None
    true_peak_db__lte: float | None = None
    true_peak_db__isnull: bool | None = None
    key_confidence__gte: float | None = None
    key_confidence__lte: float | None = None
    atonality__eq: bool | None = None
    variable_tempo__eq: bool | None = None
    danceability__gte: float | None = None
    danceability__lte: float | None = None
    danceability__isnull: bool | None = None
    dissonance_mean__gte: float | None = None
    dissonance_mean__lte: float | None = None
    bpm_confidence__gte: float | None = None
    bpm_confidence__lte: float | None = None
    bpm_confidence__isnull: bool | None = None
    bpm_stability__gte: float | None = None
    bpm_stability__lte: float | None = None
    onset_rate__gte: float | None = None
    onset_rate__lte: float | None = None
    pulse_clarity__gte: float | None = None
    pulse_clarity__lte: float | None = None
    dynamic_complexity__isnull: bool | None = None
    spectral_complexity_mean__isnull: bool | None = None
    pitch_salience_mean__isnull: bool | None = None


class TrackFeaturesCreate(BaseModel):
    """Creation triggers the audio pipeline via custom handler.

    Exactly one of ``track_id`` (single) or ``track_ids`` (batch) must
    be set. Audit iter 55 (T-53): without this guard ``entity_create
    (track_features, {"level": 3})`` leaked a bare ``KeyError:
    'track_ids'`` when the analyze handler tried to read missing keys.
    Mirrors the equivalent guard on ``AudioFileCreate``.
    """

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = None
    track_ids: list[int] | None = None
    level: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        has_single = self.track_id is not None
        has_batch = self.track_ids is not None
        if has_single == has_batch:
            raise ValueError(
                "TrackFeaturesCreate requires exactly one of 'track_id' or 'track_ids'"
            )
        if has_batch and not self.track_ids:
            raise ValueError("'track_ids' must contain at least one id")
        return self


class TrackFeaturesUpdate(BaseModel):
    """Reanalyze with a higher level."""

    model_config = ConfigDict(extra="forbid")
    level: int = Field(..., ge=1, le=5)
