"""Techno-audit / quality-gate thresholds (v2 fork).

Thresholds consumed by ``app.domain.audit.rules`` to decide whether a
track meets the techno-quality bar used by ``audit_playlist`` and friends.
Forked copy of the ``techno_*`` / ``audit_*`` fields from legacy ``app.config``.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditSettings(BaseSettings):
    """Techno audit thresholds — read from env with prefix ``DJ_``."""

    model_config = SettingsConfigDict(env_prefix="DJ_", extra="ignore")

    # ── Techno BPM window ──
    techno_bpm_min: float = Field(default=120.0, ge=20.0, le=300.0)
    techno_bpm_max: float = Field(default=155.0, ge=20.0, le=300.0)

    # ── Techno loudness window ──
    techno_lufs_min: float = Field(default=-20.0, le=0.0)
    techno_lufs_max: float = Field(default=-4.0, le=0.0)

    # ── Techno energy / rhythm floors ──
    techno_energy_min: float = Field(default=0.05, ge=0.0, le=1.0)
    techno_onset_rate_min: float = Field(default=1.0, ge=0.0)
    techno_kick_prominence_min: float = Field(default=0.05, ge=0.0, le=1.0)
    techno_pulse_clarity_min: float = Field(default=0.02, ge=0.0, le=1.0)

    # ── Techno timbre constraints ──
    techno_hp_ratio_max: float = Field(default=8.0, ge=0.0)
    techno_centroid_min: float = Field(default=300.0, ge=0.0)  # Hz
    techno_centroid_max: float = Field(default=10_000.0, ge=0.0)  # Hz
    techno_flatness_max: float = Field(default=0.5, ge=0.0, le=1.0)

    # ── Techno confidence / stability floors ──
    techno_tempo_confidence_min: float = Field(default=0.10, ge=0.0, le=1.0)
    techno_bpm_stability_min: float = Field(default=0.15, ge=0.0, le=1.0)

    # ── Techno dynamics / HNR ──
    techno_crest_factor_max: float = Field(default=30.0, ge=0.0)  # dB
    techno_lra_max: float = Field(default=25.0, ge=0.0)  # LU
    techno_hnr_min: float = Field(default=-30.0)  # dB

    # ── Audit-specific gates ──
    # Loosened from -0.3 dBTP (smoke test 2026-05-07): modern techno mastering
    # routinely sits at +0.0..+1.0 dBTP. Snapshot 2026-05-07 of
    # ``track_audio_features_computed.true_peak_db`` (~24k rows): ~17k tracks
    # have ``true_peak_db ≥ -0.5``; ~12k have ``true_peak_db ≥ +0.0``. With
    # the prior -0.3 cap audit returned ``passed=0/N`` for every playlist
    # — useless. ``0.0`` keeps the rule meaningful (flags genuine positive
    # clipping) without false-failing every mastered track.
    audit_true_peak_max: float = Field(default=0.0, le=0.0)  # dB
    audit_bpm_confidence_min: float = Field(default=0.5, ge=0.0, le=1.0)
    audit_key_confidence_min: float = Field(default=0.4, ge=0.0, le=1.0)
    audit_hp_ratio_max: float = Field(default=8.0, ge=0.0)
    audit_crest_factor_max: float = Field(default=30.0, ge=0.0)  # dB
    audit_spectral_flatness_max: float = Field(default=0.5, ge=0.0, le=1.0)
