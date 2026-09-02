# ruff: noqa: UP042, RUF002, RUF003
"""Curate schemas: TrackFeatureFilters (83 поля), Preset, CurateByRoleResult."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Preset(str, Enum):
    """Пресет курирования — гибрид filters + preset."""

    liebing_hypnotic = "liebing_hypnotic"
    liebing_industrial = "liebing_industrial"
    peak_time = "peak_time"
    custom = "custom"


class TrackRef(BaseModel):
    """Минимальная ссылка на трек для результата курирования."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    bpm: float | None = None
    key_code: int | None = None


class CurateByRoleResult(BaseModel):
    """Результат курирования по роли."""

    model_config = ConfigDict(from_attributes=True)

    tracks: list[TrackRef] = Field(default_factory=list)


class TrackFeatureFilters(BaseModel):
    """Фильтры по track_audio_features_computed (83 колонки, все Optional).

    Каждая колонка доступна через Django-style lookup:
    - числовые: __gte, __lte, __range, __isnull (+ __eq/__in для int)
    - bool: __eq
    - строковые: __eq, __in, __icontains, __isnull
    Все поля Optional, extra=forbid — точное соответствие контракту.
    """

    model_config = ConfigDict(extra="forbid")

    bpm__range: tuple[float, float] | None = Field(None, description="BPM коридор, 8-10 окно")
    integrated_lufs__range: tuple[float, float] | None = Field(None, description="LUFS 5-6 окно")
    energy_low__gte: float | None = Field(None, ge=0, le=1, description="energy_low ≥")
    spectral_centroid_hz__lte: float | None = Field(
        None, ge=0, description="spectral_centroid_hz ≤"
    )
    key_code__in: list[int] | None = Field(None, description="Camelot codes 0-23")
    atonality__eq: bool | None = None
    phrase_boundaries_ms__isnull: bool | None = None
    variable_tempo__eq: bool | None = Field(default=False, description="исключить дрейфующие")

    pipeline_run_id__eq: int | None = Field(None, description="pipeline_run_id =")
    pipeline_run_id__in: list[int] | None = Field(None, description="pipeline_run_id in")
    pipeline_run_id__gte: int | None = Field(None, description="pipeline_run_id ≥")
    pipeline_run_id__lte: int | None = Field(None, description="pipeline_run_id ≤")
    pipeline_run_id__range: tuple[int, int] | None = Field(
        None, description="pipeline_run_id range"
    )
    pipeline_run_id__isnull: bool | None = None
    analysis_level__eq: int | None = Field(None, description="analysis_level =")
    analysis_level__in: list[int] | None = Field(None, description="analysis_level in")
    analysis_level__gte: int | None = Field(None, description="analysis_level ≥")
    analysis_level__lte: int | None = Field(None, description="analysis_level ≤")
    analysis_level__range: tuple[int, int] | None = Field(None, description="analysis_level range")
    analysis_level__isnull: bool | None = None
    key_code__eq: int | None = Field(None, description="key_code =")
    key_code__gte: int | None = Field(None, description="key_code ≥")
    key_code__lte: int | None = Field(None, description="key_code ≤")
    key_code__range: tuple[int, int] | None = Field(None, description="key_code range")
    key_code__isnull: bool | None = None
    dominant_phrase_bars__eq: int | None = Field(None, description="dominant_phrase_bars =")
    dominant_phrase_bars__in: list[int] | None = Field(None, description="dominant_phrase_bars in")
    dominant_phrase_bars__gte: int | None = Field(None, description="dominant_phrase_bars ≥")
    dominant_phrase_bars__lte: int | None = Field(None, description="dominant_phrase_bars ≤")
    dominant_phrase_bars__range: tuple[int, int] | None = Field(
        None, description="dominant_phrase_bars range"
    )
    dominant_phrase_bars__isnull: bool | None = None
    audio_key_code__eq: int | None = Field(None, description="audio_key_code =")
    audio_key_code__in: list[int] | None = Field(None, description="audio_key_code in")
    audio_key_code__gte: int | None = Field(None, description="audio_key_code ≥")
    audio_key_code__lte: int | None = Field(None, description="audio_key_code ≤")
    audio_key_code__range: tuple[int, int] | None = Field(None, description="audio_key_code range")
    audio_key_code__isnull: bool | None = None
    beatport_track_id__eq: int | None = Field(None, description="beatport_track_id =")
    beatport_track_id__in: list[int] | None = Field(None, description="beatport_track_id in")
    beatport_track_id__gte: int | None = Field(None, description="beatport_track_id ≥")
    beatport_track_id__lte: int | None = Field(None, description="beatport_track_id ≤")
    beatport_track_id__range: tuple[int, int] | None = Field(
        None, description="beatport_track_id range"
    )
    beatport_track_id__isnull: bool | None = None
    beatport_duration_ms__eq: int | None = Field(None, description="beatport_duration_ms =")
    beatport_duration_ms__in: list[int] | None = Field(None, description="beatport_duration_ms in")
    beatport_duration_ms__gte: int | None = Field(None, description="beatport_duration_ms ≥")
    beatport_duration_ms__lte: int | None = Field(None, description="beatport_duration_ms ≤")
    beatport_duration_ms__range: tuple[int, int] | None = Field(
        None, description="beatport_duration_ms range"
    )
    beatport_duration_ms__isnull: bool | None = None
    variable_tempo__isnull: bool | None = None
    atonality__isnull: bool | None = None
    mfcc_vector__eq: str | None = Field(None, description="mfcc_vector =")
    mfcc_vector__in: list[str] | None = Field(None, description="mfcc_vector in")
    mfcc_vector__icontains: str | None = Field(None, description="mfcc_vector icontains")
    mfcc_vector__isnull: bool | None = None
    tonnetz_vector__eq: str | None = Field(None, description="tonnetz_vector =")
    tonnetz_vector__in: list[str] | None = Field(None, description="tonnetz_vector in")
    tonnetz_vector__icontains: str | None = Field(None, description="tonnetz_vector icontains")
    tonnetz_vector__isnull: bool | None = None
    tempogram_ratio_vector__eq: str | None = Field(None, description="tempogram_ratio_vector =")
    tempogram_ratio_vector__in: list[str] | None = Field(
        None, description="tempogram_ratio_vector in"
    )
    tempogram_ratio_vector__icontains: str | None = Field(
        None, description="tempogram_ratio_vector icontains"
    )
    tempogram_ratio_vector__isnull: bool | None = None
    beat_loudness_band_ratio__eq: str | None = Field(
        None, description="beat_loudness_band_ratio ="
    )
    beat_loudness_band_ratio__in: list[str] | None = Field(
        None, description="beat_loudness_band_ratio in"
    )
    beat_loudness_band_ratio__icontains: str | None = Field(
        None, description="beat_loudness_band_ratio icontains"
    )
    beat_loudness_band_ratio__isnull: bool | None = None
    phrase_boundaries_ms__eq: str | None = Field(None, description="phrase_boundaries_ms =")
    phrase_boundaries_ms__in: list[str] | None = Field(None, description="phrase_boundaries_ms in")
    phrase_boundaries_ms__icontains: str | None = Field(
        None, description="phrase_boundaries_ms icontains"
    )
    mood__eq: str | None = Field(None, description="mood =")
    mood__in: list[str] | None = Field(None, description="mood in")
    mood__icontains: str | None = Field(None, description="mood icontains")
    mood__isnull: bool | None = None
    mood_source__eq: str | None = Field(None, description="mood_source =")
    mood_source__in: list[str] | None = Field(None, description="mood_source in")
    mood_source__icontains: str | None = Field(None, description="mood_source icontains")
    mood_source__isnull: bool | None = None
    audio_mood__eq: str | None = Field(None, description="audio_mood =")
    audio_mood__in: list[str] | None = Field(None, description="audio_mood in")
    audio_mood__icontains: str | None = Field(None, description="audio_mood icontains")
    audio_mood__isnull: bool | None = None
    bpm_source__eq: str | None = Field(None, description="bpm_source =")
    bpm_source__in: list[str] | None = Field(None, description="bpm_source in")
    bpm_source__icontains: str | None = Field(None, description="bpm_source icontains")
    bpm_source__isnull: bool | None = None
    key_source__eq: str | None = Field(None, description="key_source =")
    key_source__in: list[str] | None = Field(None, description="key_source in")
    key_source__icontains: str | None = Field(None, description="key_source icontains")
    key_source__isnull: bool | None = None
    beatport_genre__eq: str | None = Field(None, description="beatport_genre =")
    beatport_genre__in: list[str] | None = Field(None, description="beatport_genre in")
    beatport_genre__icontains: str | None = Field(None, description="beatport_genre icontains")
    beatport_genre__isnull: bool | None = None
    beatport_sub_genre__eq: str | None = Field(None, description="beatport_sub_genre =")
    beatport_sub_genre__in: list[str] | None = Field(None, description="beatport_sub_genre in")
    beatport_sub_genre__icontains: str | None = Field(
        None, description="beatport_sub_genre icontains"
    )
    beatport_sub_genre__isnull: bool | None = None
    beatport_confidence__eq: str | None = Field(None, description="beatport_confidence =")
    beatport_confidence__in: list[str] | None = Field(None, description="beatport_confidence in")
    beatport_confidence__icontains: str | None = Field(
        None, description="beatport_confidence icontains"
    )
    beatport_confidence__isnull: bool | None = None
    beatport_key__eq: str | None = Field(None, description="beatport_key =")
    beatport_key__in: list[str] | None = Field(None, description="beatport_key in")
    beatport_key__icontains: str | None = Field(None, description="beatport_key icontains")
    beatport_key__isnull: bool | None = None
    beatport_camelot__eq: str | None = Field(None, description="beatport_camelot =")
    beatport_camelot__in: list[str] | None = Field(None, description="beatport_camelot in")
    beatport_camelot__icontains: str | None = Field(None, description="beatport_camelot icontains")
    beatport_camelot__isnull: bool | None = None
    beatport_isrc__eq: str | None = Field(None, description="beatport_isrc =")
    beatport_isrc__in: list[str] | None = Field(None, description="beatport_isrc in")
    beatport_isrc__icontains: str | None = Field(None, description="beatport_isrc icontains")
    beatport_isrc__isnull: bool | None = None
    beatport_release__eq: str | None = Field(None, description="beatport_release =")
    beatport_release__in: list[str] | None = Field(None, description="beatport_release in")
    beatport_release__icontains: str | None = Field(None, description="beatport_release icontains")
    beatport_release__isnull: bool | None = None
    beatport_label__eq: str | None = Field(None, description="beatport_label =")
    beatport_label__in: list[str] | None = Field(None, description="beatport_label in")
    beatport_label__icontains: str | None = Field(None, description="beatport_label icontains")
    beatport_label__isnull: bool | None = None
    bpm__gte: float | None = Field(None, ge=20, le=300, description="bpm")
    bpm__lte: float | None = Field(None, ge=20, le=300, description="bpm")
    bpm__isnull: bool | None = None
    bpm__eq: float | None = Field(None, ge=20, le=300, description="bpm")
    bpm_confidence__gte: float | None = Field(None, description="bpm_confidence ≥")
    bpm_confidence__lte: float | None = Field(None, description="bpm_confidence ≤")
    bpm_confidence__range: tuple[float, float] | None = Field(
        None, description="bpm_confidence range"
    )
    bpm_confidence__isnull: bool | None = None
    bpm_confidence__eq: float | None = Field(None, description="bpm_confidence =")
    bpm_stability__gte: float | None = Field(None, description="bpm_stability ≥")
    bpm_stability__lte: float | None = Field(None, description="bpm_stability ≤")
    bpm_stability__range: tuple[float, float] | None = Field(
        None, description="bpm_stability range"
    )
    bpm_stability__isnull: bool | None = None
    bpm_stability__eq: float | None = Field(None, description="bpm_stability =")
    integrated_lufs__gte: float | None = Field(None, description="integrated_lufs ≥")
    integrated_lufs__lte: float | None = Field(None, description="integrated_lufs ≤")
    integrated_lufs__isnull: bool | None = None
    integrated_lufs__eq: float | None = Field(None, description="integrated_lufs =")
    short_term_lufs_mean__gte: float | None = Field(None, description="short_term_lufs_mean ≥")
    short_term_lufs_mean__lte: float | None = Field(None, description="short_term_lufs_mean ≤")
    short_term_lufs_mean__range: tuple[float, float] | None = Field(
        None, description="short_term_lufs_mean range"
    )
    short_term_lufs_mean__isnull: bool | None = None
    short_term_lufs_mean__eq: float | None = Field(None, description="short_term_lufs_mean =")
    momentary_max__gte: float | None = Field(None, description="momentary_max ≥")
    momentary_max__lte: float | None = Field(None, description="momentary_max ≤")
    momentary_max__range: tuple[float, float] | None = Field(
        None, description="momentary_max range"
    )
    momentary_max__isnull: bool | None = None
    momentary_max__eq: float | None = Field(None, description="momentary_max =")
    rms_dbfs__gte: float | None = Field(None, description="rms_dbfs ≥")
    rms_dbfs__lte: float | None = Field(None, description="rms_dbfs ≤")
    rms_dbfs__range: tuple[float, float] | None = Field(None, description="rms_dbfs range")
    rms_dbfs__isnull: bool | None = None
    rms_dbfs__eq: float | None = Field(None, description="rms_dbfs =")
    true_peak_db__gte: float | None = Field(None, description="true_peak_db ≥")
    true_peak_db__lte: float | None = Field(None, description="true_peak_db ≤")
    true_peak_db__range: tuple[float, float] | None = Field(None, description="true_peak_db range")
    true_peak_db__isnull: bool | None = None
    true_peak_db__eq: float | None = Field(None, description="true_peak_db =")
    crest_factor_db__gte: float | None = Field(None, description="crest_factor_db ≥")
    crest_factor_db__lte: float | None = Field(None, description="crest_factor_db ≤")
    crest_factor_db__range: tuple[float, float] | None = Field(
        None, description="crest_factor_db range"
    )
    crest_factor_db__isnull: bool | None = None
    crest_factor_db__eq: float | None = Field(None, description="crest_factor_db =")
    loudness_range_lu__gte: float | None = Field(None, description="loudness_range_lu ≥")
    loudness_range_lu__lte: float | None = Field(None, description="loudness_range_lu ≤")
    loudness_range_lu__range: tuple[float, float] | None = Field(
        None, description="loudness_range_lu range"
    )
    loudness_range_lu__isnull: bool | None = None
    loudness_range_lu__eq: float | None = Field(None, description="loudness_range_lu =")
    energy_mean__gte: float | None = Field(None, ge=0, le=1, description="energy_mean")
    energy_mean__lte: float | None = Field(None, ge=0, le=1, description="energy_mean")
    energy_mean__range: tuple[float, float] | None = Field(
        None, description="energy_mean range 0-1"
    )
    energy_mean__isnull: bool | None = None
    energy_mean__eq: float | None = Field(None, ge=0, le=1, description="energy_mean")
    energy_max__gte: float | None = Field(None, ge=0, le=1, description="energy_max")
    energy_max__lte: float | None = Field(None, ge=0, le=1, description="energy_max")
    energy_max__range: tuple[float, float] | None = Field(None, description="energy_max range 0-1")
    energy_max__isnull: bool | None = None
    energy_max__eq: float | None = Field(None, ge=0, le=1, description="energy_max")
    energy_std__gte: float | None = Field(None, ge=0, le=1, description="energy_std")
    energy_std__lte: float | None = Field(None, ge=0, le=1, description="energy_std")
    energy_std__range: tuple[float, float] | None = Field(None, description="energy_std range 0-1")
    energy_std__isnull: bool | None = None
    energy_std__eq: float | None = Field(None, ge=0, le=1, description="energy_std")
    energy_slope__gte: float | None = Field(None, ge=0, le=1, description="energy_slope")
    energy_slope__lte: float | None = Field(None, ge=0, le=1, description="energy_slope")
    energy_slope__range: tuple[float, float] | None = Field(
        None, description="energy_slope range 0-1"
    )
    energy_slope__isnull: bool | None = None
    energy_slope__eq: float | None = Field(None, ge=0, le=1, description="energy_slope")
    energy_sub__gte: float | None = Field(None, ge=0, le=1, description="energy_sub")
    energy_sub__lte: float | None = Field(None, ge=0, le=1, description="energy_sub")
    energy_sub__range: tuple[float, float] | None = Field(None, description="energy_sub range 0-1")
    energy_sub__isnull: bool | None = None
    energy_sub__eq: float | None = Field(None, ge=0, le=1, description="energy_sub")
    energy_low__lte: float | None = Field(None, ge=0, le=1, description="energy_low")
    energy_low__range: tuple[float, float] | None = Field(None, description="energy_low range 0-1")
    energy_low__isnull: bool | None = None
    energy_low__eq: float | None = Field(None, ge=0, le=1, description="energy_low")
    energy_lowmid__gte: float | None = Field(None, ge=0, le=1, description="energy_lowmid")
    energy_lowmid__lte: float | None = Field(None, ge=0, le=1, description="energy_lowmid")
    energy_lowmid__range: tuple[float, float] | None = Field(
        None, description="energy_lowmid range 0-1"
    )
    energy_lowmid__isnull: bool | None = None
    energy_lowmid__eq: float | None = Field(None, ge=0, le=1, description="energy_lowmid")
    energy_mid__gte: float | None = Field(None, ge=0, le=1, description="energy_mid")
    energy_mid__lte: float | None = Field(None, ge=0, le=1, description="energy_mid")
    energy_mid__range: tuple[float, float] | None = Field(None, description="energy_mid range 0-1")
    energy_mid__isnull: bool | None = None
    energy_mid__eq: float | None = Field(None, ge=0, le=1, description="energy_mid")
    energy_highmid__gte: float | None = Field(None, ge=0, le=1, description="energy_highmid")
    energy_highmid__lte: float | None = Field(None, ge=0, le=1, description="energy_highmid")
    energy_highmid__range: tuple[float, float] | None = Field(
        None, description="energy_highmid range 0-1"
    )
    energy_highmid__isnull: bool | None = None
    energy_highmid__eq: float | None = Field(None, ge=0, le=1, description="energy_highmid")
    energy_high__gte: float | None = Field(None, ge=0, le=1, description="energy_high")
    energy_high__lte: float | None = Field(None, ge=0, le=1, description="energy_high")
    energy_high__range: tuple[float, float] | None = Field(
        None, description="energy_high range 0-1"
    )
    energy_high__isnull: bool | None = None
    energy_high__eq: float | None = Field(None, ge=0, le=1, description="energy_high")
    energy_sub_ratio__gte: float | None = Field(None, ge=0, le=1, description="energy_sub_ratio")
    energy_sub_ratio__lte: float | None = Field(None, ge=0, le=1, description="energy_sub_ratio")
    energy_sub_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_sub_ratio range 0-1"
    )
    energy_sub_ratio__isnull: bool | None = None
    energy_sub_ratio__eq: float | None = Field(None, ge=0, le=1, description="energy_sub_ratio")
    energy_low_ratio__gte: float | None = Field(None, ge=0, le=1, description="energy_low_ratio")
    energy_low_ratio__lte: float | None = Field(None, ge=0, le=1, description="energy_low_ratio")
    energy_low_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_low_ratio range 0-1"
    )
    energy_low_ratio__isnull: bool | None = None
    energy_low_ratio__eq: float | None = Field(None, ge=0, le=1, description="energy_low_ratio")
    energy_lowmid_ratio__gte: float | None = Field(
        None, ge=0, le=1, description="energy_lowmid_ratio"
    )
    energy_lowmid_ratio__lte: float | None = Field(
        None, ge=0, le=1, description="energy_lowmid_ratio"
    )
    energy_lowmid_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_lowmid_ratio range 0-1"
    )
    energy_lowmid_ratio__isnull: bool | None = None
    energy_lowmid_ratio__eq: float | None = Field(
        None, ge=0, le=1, description="energy_lowmid_ratio"
    )
    energy_mid_ratio__gte: float | None = Field(None, ge=0, le=1, description="energy_mid_ratio")
    energy_mid_ratio__lte: float | None = Field(None, ge=0, le=1, description="energy_mid_ratio")
    energy_mid_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_mid_ratio range 0-1"
    )
    energy_mid_ratio__isnull: bool | None = None
    energy_mid_ratio__eq: float | None = Field(None, ge=0, le=1, description="energy_mid_ratio")
    energy_highmid_ratio__gte: float | None = Field(
        None, ge=0, le=1, description="energy_highmid_ratio"
    )
    energy_highmid_ratio__lte: float | None = Field(
        None, ge=0, le=1, description="energy_highmid_ratio"
    )
    energy_highmid_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_highmid_ratio range 0-1"
    )
    energy_highmid_ratio__isnull: bool | None = None
    energy_highmid_ratio__eq: float | None = Field(
        None, ge=0, le=1, description="energy_highmid_ratio"
    )
    energy_high_ratio__gte: float | None = Field(None, ge=0, le=1, description="energy_high_ratio")
    energy_high_ratio__lte: float | None = Field(None, ge=0, le=1, description="energy_high_ratio")
    energy_high_ratio__range: tuple[float, float] | None = Field(
        None, description="energy_high_ratio range 0-1"
    )
    energy_high_ratio__isnull: bool | None = None
    energy_high_ratio__eq: float | None = Field(None, ge=0, le=1, description="energy_high_ratio")
    spectral_centroid_hz__gte: float | None = Field(None, ge=0, description="spectral_centroid_hz")
    spectral_centroid_hz__range: tuple[float, float] | None = Field(
        None, description="spectral_centroid_hz range"
    )
    spectral_centroid_hz__isnull: bool | None = None
    spectral_centroid_hz__eq: float | None = Field(None, ge=0, description="spectral_centroid_hz")
    spectral_rolloff_85__gte: float | None = Field(None, description="spectral_rolloff_85 ≥")
    spectral_rolloff_85__lte: float | None = Field(None, description="spectral_rolloff_85 ≤")
    spectral_rolloff_85__range: tuple[float, float] | None = Field(
        None, description="spectral_rolloff_85 range"
    )
    spectral_rolloff_85__isnull: bool | None = None
    spectral_rolloff_85__eq: float | None = Field(None, description="spectral_rolloff_85 =")
    spectral_rolloff_95__gte: float | None = Field(None, description="spectral_rolloff_95 ≥")
    spectral_rolloff_95__lte: float | None = Field(None, description="spectral_rolloff_95 ≤")
    spectral_rolloff_95__range: tuple[float, float] | None = Field(
        None, description="spectral_rolloff_95 range"
    )
    spectral_rolloff_95__isnull: bool | None = None
    spectral_rolloff_95__eq: float | None = Field(None, description="spectral_rolloff_95 =")
    spectral_flatness__gte: float | None = Field(None, ge=0, le=1, description="spectral_flatness")
    spectral_flatness__lte: float | None = Field(None, ge=0, le=1, description="spectral_flatness")
    spectral_flatness__range: tuple[float, float] | None = Field(
        None, description="spectral_flatness range 0-1"
    )
    spectral_flatness__isnull: bool | None = None
    spectral_flatness__eq: float | None = Field(None, ge=0, le=1, description="spectral_flatness")
    spectral_flux_mean__gte: float | None = Field(None, description="spectral_flux_mean ≥")
    spectral_flux_mean__lte: float | None = Field(None, description="spectral_flux_mean ≤")
    spectral_flux_mean__range: tuple[float, float] | None = Field(
        None, description="spectral_flux_mean range"
    )
    spectral_flux_mean__isnull: bool | None = None
    spectral_flux_mean__eq: float | None = Field(None, description="spectral_flux_mean =")
    spectral_flux_std__gte: float | None = Field(None, description="spectral_flux_std ≥")
    spectral_flux_std__lte: float | None = Field(None, description="spectral_flux_std ≤")
    spectral_flux_std__range: tuple[float, float] | None = Field(
        None, description="spectral_flux_std range"
    )
    spectral_flux_std__isnull: bool | None = None
    spectral_flux_std__eq: float | None = Field(None, description="spectral_flux_std =")
    spectral_slope__gte: float | None = Field(None, description="spectral_slope ≥")
    spectral_slope__lte: float | None = Field(None, description="spectral_slope ≤")
    spectral_slope__range: tuple[float, float] | None = Field(
        None, description="spectral_slope range"
    )
    spectral_slope__isnull: bool | None = None
    spectral_slope__eq: float | None = Field(None, description="spectral_slope =")
    spectral_contrast__gte: float | None = Field(None, description="spectral_contrast ≥")
    spectral_contrast__lte: float | None = Field(None, description="spectral_contrast ≤")
    spectral_contrast__range: tuple[float, float] | None = Field(
        None, description="spectral_contrast range"
    )
    spectral_contrast__isnull: bool | None = None
    spectral_contrast__eq: float | None = Field(None, description="spectral_contrast =")
    key_confidence__gte: float | None = Field(None, description="key_confidence ≥")
    key_confidence__lte: float | None = Field(None, description="key_confidence ≤")
    key_confidence__range: tuple[float, float] | None = Field(
        None, description="key_confidence range"
    )
    key_confidence__isnull: bool | None = None
    key_confidence__eq: float | None = Field(None, description="key_confidence =")
    hnr_db__gte: float | None = Field(None, description="hnr_db ≥")
    hnr_db__lte: float | None = Field(None, description="hnr_db ≤")
    hnr_db__range: tuple[float, float] | None = Field(None, description="hnr_db range")
    hnr_db__isnull: bool | None = None
    hnr_db__eq: float | None = Field(None, description="hnr_db =")
    chroma_entropy__gte: float | None = Field(None, description="chroma_entropy ≥")
    chroma_entropy__lte: float | None = Field(None, description="chroma_entropy ≤")
    chroma_entropy__range: tuple[float, float] | None = Field(
        None, description="chroma_entropy range"
    )
    chroma_entropy__isnull: bool | None = None
    chroma_entropy__eq: float | None = Field(None, description="chroma_entropy =")
    hp_ratio__gte: float | None = Field(None, description="hp_ratio ≥")
    hp_ratio__lte: float | None = Field(None, description="hp_ratio ≤")
    hp_ratio__range: tuple[float, float] | None = Field(None, description="hp_ratio range")
    hp_ratio__isnull: bool | None = None
    hp_ratio__eq: float | None = Field(None, description="hp_ratio =")
    onset_rate__gte: float | None = Field(None, description="onset_rate ≥")
    onset_rate__lte: float | None = Field(None, description="onset_rate ≤")
    onset_rate__range: tuple[float, float] | None = Field(None, description="onset_rate range")
    onset_rate__isnull: bool | None = None
    onset_rate__eq: float | None = Field(None, description="onset_rate =")
    pulse_clarity__gte: float | None = Field(None, description="pulse_clarity ≥")
    pulse_clarity__lte: float | None = Field(None, description="pulse_clarity ≤")
    pulse_clarity__range: tuple[float, float] | None = Field(
        None, description="pulse_clarity range"
    )
    pulse_clarity__isnull: bool | None = None
    pulse_clarity__eq: float | None = Field(None, description="pulse_clarity =")
    kick_prominence__gte: float | None = Field(None, description="kick_prominence ≥")
    kick_prominence__lte: float | None = Field(None, description="kick_prominence ≤")
    kick_prominence__range: tuple[float, float] | None = Field(
        None, description="kick_prominence range"
    )
    kick_prominence__isnull: bool | None = None
    kick_prominence__eq: float | None = Field(None, description="kick_prominence =")
    danceability__gte: float | None = Field(None, ge=0, le=1, description="danceability")
    danceability__lte: float | None = Field(None, ge=0, le=1, description="danceability")
    danceability__range: tuple[float, float] | None = Field(
        None, description="danceability range 0-1"
    )
    danceability__isnull: bool | None = None
    danceability__eq: float | None = Field(None, ge=0, le=1, description="danceability")
    dynamic_complexity__gte: float | None = Field(
        None, ge=0, le=1, description="dynamic_complexity"
    )
    dynamic_complexity__lte: float | None = Field(
        None, ge=0, le=1, description="dynamic_complexity"
    )
    dynamic_complexity__range: tuple[float, float] | None = Field(
        None, description="dynamic_complexity range 0-1"
    )
    dynamic_complexity__isnull: bool | None = None
    dynamic_complexity__eq: float | None = Field(
        None, ge=0, le=1, description="dynamic_complexity"
    )
    dissonance_mean__gte: float | None = Field(None, description="dissonance_mean ≥")
    dissonance_mean__lte: float | None = Field(None, description="dissonance_mean ≤")
    dissonance_mean__range: tuple[float, float] | None = Field(
        None, description="dissonance_mean range"
    )
    dissonance_mean__isnull: bool | None = None
    dissonance_mean__eq: float | None = Field(None, description="dissonance_mean =")
    spectral_complexity_mean__gte: float | None = Field(
        None, description="spectral_complexity_mean ≥"
    )
    spectral_complexity_mean__lte: float | None = Field(
        None, description="spectral_complexity_mean ≤"
    )
    spectral_complexity_mean__range: tuple[float, float] | None = Field(
        None, description="spectral_complexity_mean range"
    )
    spectral_complexity_mean__isnull: bool | None = None
    spectral_complexity_mean__eq: float | None = Field(
        None, description="spectral_complexity_mean ="
    )
    pitch_salience_mean__gte: float | None = Field(None, description="pitch_salience_mean ≥")
    pitch_salience_mean__lte: float | None = Field(None, description="pitch_salience_mean ≤")
    pitch_salience_mean__range: tuple[float, float] | None = Field(
        None, description="pitch_salience_mean range"
    )
    pitch_salience_mean__isnull: bool | None = None
    pitch_salience_mean__eq: float | None = Field(None, description="pitch_salience_mean =")
    bpm_histogram_first_peak_weight__gte: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_first_peak_weight"
    )
    bpm_histogram_first_peak_weight__lte: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_first_peak_weight"
    )
    bpm_histogram_first_peak_weight__range: tuple[float, float] | None = Field(
        None, description="bpm_histogram_first_peak_weight range 0-1"
    )
    bpm_histogram_first_peak_weight__isnull: bool | None = None
    bpm_histogram_first_peak_weight__eq: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_first_peak_weight"
    )
    bpm_histogram_second_peak_bpm__gte: float | None = Field(
        None, description="bpm_histogram_second_peak_bpm ≥"
    )
    bpm_histogram_second_peak_bpm__lte: float | None = Field(
        None, description="bpm_histogram_second_peak_bpm ≤"
    )
    bpm_histogram_second_peak_bpm__range: tuple[float, float] | None = Field(
        None, description="bpm_histogram_second_peak_bpm range"
    )
    bpm_histogram_second_peak_bpm__isnull: bool | None = None
    bpm_histogram_second_peak_bpm__eq: float | None = Field(
        None, description="bpm_histogram_second_peak_bpm ="
    )
    bpm_histogram_second_peak_weight__gte: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_second_peak_weight"
    )
    bpm_histogram_second_peak_weight__lte: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_second_peak_weight"
    )
    bpm_histogram_second_peak_weight__range: tuple[float, float] | None = Field(
        None, description="bpm_histogram_second_peak_weight range 0-1"
    )
    bpm_histogram_second_peak_weight__isnull: bool | None = None
    bpm_histogram_second_peak_weight__eq: float | None = Field(
        None, ge=0, le=1, description="bpm_histogram_second_peak_weight"
    )
    first_downbeat_ms__gte: float | None = Field(None, description="first_downbeat_ms ≥")
    first_downbeat_ms__lte: float | None = Field(None, description="first_downbeat_ms ≤")
    first_downbeat_ms__range: tuple[float, float] | None = Field(
        None, description="first_downbeat_ms range"
    )
    first_downbeat_ms__isnull: bool | None = None
    first_downbeat_ms__eq: float | None = Field(None, description="first_downbeat_ms =")
    mood_confidence__gte: float | None = Field(None, description="mood_confidence ≥")
    mood_confidence__lte: float | None = Field(None, description="mood_confidence ≤")
    mood_confidence__range: tuple[float, float] | None = Field(
        None, description="mood_confidence range"
    )
    mood_confidence__isnull: bool | None = None
    mood_confidence__eq: float | None = Field(None, description="mood_confidence =")
    audio_bpm__gte: float | None = Field(None, description="audio_bpm ≥")
    audio_bpm__lte: float | None = Field(None, description="audio_bpm ≤")
    audio_bpm__range: tuple[float, float] | None = Field(None, description="audio_bpm range")
    audio_bpm__isnull: bool | None = None
    audio_bpm__eq: float | None = Field(None, description="audio_bpm =")
    audio_bpm_confidence__gte: float | None = Field(None, description="audio_bpm_confidence ≥")
    audio_bpm_confidence__lte: float | None = Field(None, description="audio_bpm_confidence ≤")
    audio_bpm_confidence__range: tuple[float, float] | None = Field(
        None, description="audio_bpm_confidence range"
    )
    audio_bpm_confidence__isnull: bool | None = None
    audio_bpm_confidence__eq: float | None = Field(None, description="audio_bpm_confidence =")
    audio_key_confidence__gte: float | None = Field(None, description="audio_key_confidence ≥")
    audio_key_confidence__lte: float | None = Field(None, description="audio_key_confidence ≤")
    audio_key_confidence__range: tuple[float, float] | None = Field(
        None, description="audio_key_confidence range"
    )
    audio_key_confidence__isnull: bool | None = None
    audio_key_confidence__eq: float | None = Field(None, description="audio_key_confidence =")
    audio_mood_confidence__gte: float | None = Field(None, description="audio_mood_confidence ≥")
    audio_mood_confidence__lte: float | None = Field(None, description="audio_mood_confidence ≤")
    audio_mood_confidence__range: tuple[float, float] | None = Field(
        None, description="audio_mood_confidence range"
    )
    audio_mood_confidence__isnull: bool | None = None
    audio_mood_confidence__eq: float | None = Field(None, description="audio_mood_confidence =")
    beatport_bpm__gte: float | None = Field(None, description="beatport_bpm ≥")
    beatport_bpm__lte: float | None = Field(None, description="beatport_bpm ≤")
    beatport_bpm__range: tuple[float, float] | None = Field(None, description="beatport_bpm range")
    beatport_bpm__isnull: bool | None = None
    beatport_bpm__eq: float | None = Field(None, description="beatport_bpm =")

    # Всего полей-фильтров: 398 (>=83)
