"""Subgenre profiles — frozen dataclasses replacing 122-line inline dict.

Each profile defines feature targets for one of 15 techno subgenres.
Profiles are immutable and type-safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import TechnoSubgenre


@dataclass(frozen=True, slots=True)
class FeatureTarget:
    """Target for a single audio feature within a subgenre profile."""

    weight: float
    ideal: float
    tolerance: float


@dataclass(frozen=True, slots=True)
class SubgenreProfile:
    """Scoring profile for one techno subgenre."""

    subgenre: TechnoSubgenre
    features: dict[str, FeatureTarget]
    catch_all_penalty: float = 0.0


# ── 15 Subgenre Profiles ──────────────────────────────────────────────

AMBIENT_DUB = SubgenreProfile(
    subgenre=TechnoSubgenre.AMBIENT_DUB,
    features={
        "energy_mean": FeatureTarget(2.0, 0.1, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.5, 800.0, 500.0),
        "spectral_flatness": FeatureTarget(1.0, 0.15, 0.1),
        "spectral_flux_std": FeatureTarget(1.0, 0.5, 0.5),
        "loudness_range_lu": FeatureTarget(1.5, 12.0, 5.0),
        "crest_factor_db": FeatureTarget(1.0, 15.0, 5.0),
        "danceability": FeatureTarget(1.5, 0.8, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.15, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.15, 0.1),
        "pitch_salience_mean": FeatureTarget(1.5, 0.45, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 8.0, 4.0),
        "hp_ratio": FeatureTarget(1.5, 4.0, 1.5),
        "pulse_clarity": FeatureTarget(1.0, 0.15, 0.1),
        "kick_prominence": FeatureTarget(1.0, 0.1, 0.1),
        "integrated_lufs": FeatureTarget(1.5, -16.0, 3.0),
    },
)

DUB_TECHNO = SubgenreProfile(
    subgenre=TechnoSubgenre.DUB_TECHNO,
    features={
        "energy_mean": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.5, 1200.0, 600.0),
        "spectral_flatness": FeatureTarget(1.0, 0.2, 0.1),
        "loudness_range_lu": FeatureTarget(2.0, 10.0, 4.0),
        "energy_low": FeatureTarget(1.5, 0.3, 0.15),
        "spectral_flux_std": FeatureTarget(1.0, 1.0, 1.0),
        "danceability": FeatureTarget(1.5, 1.2, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.2, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.2, 0.1),
        "pitch_salience_mean": FeatureTarget(1.5, 0.4, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 8.0, 3.0),
        "hp_ratio": FeatureTarget(1.5, 3.5, 1.0),
        "pulse_clarity": FeatureTarget(1.0, 0.3, 0.15),
        "spectral_contrast": FeatureTarget(1.0, 10.0, 4.0),
        "integrated_lufs": FeatureTarget(1.0, -14.0, 3.0),
    },
)

MINIMAL = SubgenreProfile(
    subgenre=TechnoSubgenre.MINIMAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.25, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 1500.0, 700.0),
        "spectral_flatness": FeatureTarget(1.5, 0.1, 0.08),
        "energy_std": FeatureTarget(1.5, 0.1, 0.08),
        "spectral_flux_std": FeatureTarget(1.0, 0.8, 0.5),
        "energy_mid": FeatureTarget(1.0, 0.15, 0.1),
        "danceability": FeatureTarget(1.5, 1.5, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.2, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.2, 0.1),
        "pitch_salience_mean": FeatureTarget(1.0, 0.2, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.5, 5.0, 2.0),
        "bpm_stability": FeatureTarget(1.0, 0.9, 0.1),
        "pulse_clarity": FeatureTarget(1.0, 0.5, 0.2),
        "onset_rate": FeatureTarget(1.5, 2.5, 1.0),
        "kick_prominence": FeatureTarget(1.0, 0.3, 0.15),
    },
)

DETROIT = SubgenreProfile(
    subgenre=TechnoSubgenre.DETROIT,
    features={
        "energy_mean": FeatureTarget(1.5, 0.4, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 2000.0, 800.0),
        "energy_mid": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 5.0, 3.0),
        "crest_factor_db": FeatureTarget(1.0, 10.0, 4.0),
        "energy_highmid": FeatureTarget(1.0, 0.15, 0.1),
        "danceability": FeatureTarget(1.5, 2.0, 0.4),
        "dissonance_mean": FeatureTarget(1.0, 0.25, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.3, 0.15),
        "pitch_salience_mean": FeatureTarget(1.5, 0.45, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 12.0, 5.0),
        "hp_ratio": FeatureTarget(1.0, 2.0, 0.7),
    },
)

MELODIC_DEEP = SubgenreProfile(
    subgenre=TechnoSubgenre.MELODIC_DEEP,
    features={
        "energy_mean": FeatureTarget(1.0, 0.35, 0.15),
        "spectral_centroid_hz": FeatureTarget(2.0, 1200.0, 500.0),
        "spectral_flatness": FeatureTarget(1.5, 0.08, 0.05),
        "energy_mid": FeatureTarget(1.5, 0.25, 0.1),
        "loudness_range_lu": FeatureTarget(1.0, 8.0, 3.0),
        "spectral_flux_std": FeatureTarget(1.0, 2.0, 1.5),
        "danceability": FeatureTarget(1.5, 1.8, 0.4),
        "dissonance_mean": FeatureTarget(1.0, 0.15, 0.08),
        "dynamic_complexity": FeatureTarget(1.0, 0.3, 0.15),
        "pitch_salience_mean": FeatureTarget(2.0, 0.55, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 10.0, 4.0),
        "hp_ratio": FeatureTarget(1.5, 2.5, 0.8),
        "pulse_clarity": FeatureTarget(1.0, 0.5, 0.2),
    },
)

PROGRESSIVE = SubgenreProfile(
    subgenre=TechnoSubgenre.PROGRESSIVE,
    features={
        "energy_mean": FeatureTarget(1.0, 0.4, 0.15),
        "energy_slope": FeatureTarget(2.0, 0.001, 0.001),
        "spectral_centroid_hz": FeatureTarget(1.0, 2000.0, 800.0),
        "energy_std": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 5.0, 3.0),
        "loudness_range_lu": FeatureTarget(1.0, 8.0, 3.0),
        "danceability": FeatureTarget(1.5, 2.0, 0.4),
        "dissonance_mean": FeatureTarget(1.0, 0.2, 0.1),
        "dynamic_complexity": FeatureTarget(1.5, 0.45, 0.15),
        "pitch_salience_mean": FeatureTarget(1.5, 0.4, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 12.0, 5.0),
        "hp_ratio": FeatureTarget(1.0, 2.0, 0.7),
    },
)

HYPNOTIC = SubgenreProfile(
    subgenre=TechnoSubgenre.HYPNOTIC,
    features={
        "energy_mean": FeatureTarget(1.0, 0.45, 0.15),
        "spectral_flux_std": FeatureTarget(2.0, 0.5, 0.4),
        "energy_std": FeatureTarget(2.0, 0.05, 0.04),
        "spectral_centroid_hz": FeatureTarget(1.0, 1800.0, 700.0),
        "spectral_flatness": FeatureTarget(1.0, 0.12, 0.08),
        "energy_low": FeatureTarget(1.0, 0.25, 0.1),
        "danceability": FeatureTarget(1.5, 2.0, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.25, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.15, 0.08),
        "pitch_salience_mean": FeatureTarget(1.5, 0.3, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 8.0, 3.0),
        "bpm_stability": FeatureTarget(1.5, 0.95, 0.03),
        "pulse_clarity": FeatureTarget(1.0, 0.6, 0.15),
    },
    catch_all_penalty=1.0,
)

DRIVING = SubgenreProfile(
    subgenre=TechnoSubgenre.DRIVING,
    features={
        "energy_mean": FeatureTarget(1.5, 0.55, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 2500.0, 1000.0),
        "energy_low": FeatureTarget(1.5, 0.25, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 8.0, 4.0),
        "crest_factor_db": FeatureTarget(1.0, 8.0, 3.0),
        "energy_std": FeatureTarget(1.0, 0.12, 0.08),
        "danceability": FeatureTarget(2.0, 2.5, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.3, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.2, 0.1),
        "pitch_salience_mean": FeatureTarget(1.0, 0.15, 0.1),
        "spectral_complexity_mean": FeatureTarget(1.0, 12.0, 5.0),
        "bpm_stability": FeatureTarget(1.5, 0.95, 0.05),
        "hp_ratio": FeatureTarget(1.0, 1.3, 0.3),
        "pulse_clarity": FeatureTarget(1.5, 0.7, 0.15),
    },
    catch_all_penalty=1.0,
)

TRIBAL = SubgenreProfile(
    subgenre=TechnoSubgenre.TRIBAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.5, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 1800.0, 700.0),
        "energy_low": FeatureTarget(2.0, 0.3, 0.12),
        "energy_sub": FeatureTarget(1.5, 0.15, 0.08),
        "spectral_flux_std": FeatureTarget(1.0, 3.0, 2.0),
        "energy_std": FeatureTarget(1.0, 0.15, 0.1),
        "danceability": FeatureTarget(1.5, 2.2, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.25, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.3, 0.15),
        "pitch_salience_mean": FeatureTarget(1.0, 0.15, 0.1),
        "spectral_complexity_mean": FeatureTarget(1.0, 10.0, 4.0),
        "bpm_stability": FeatureTarget(1.5, 0.8, 0.1),
        "pulse_clarity": FeatureTarget(1.5, 0.6, 0.15),
        "onset_rate": FeatureTarget(1.5, 5.0, 1.5),
        "bpm_histogram_first_peak_weight": FeatureTarget(1.5, 0.5, 0.15),
    },
)

BREAKBEAT = SubgenreProfile(
    subgenre=TechnoSubgenre.BREAKBEAT,
    features={
        "energy_mean": FeatureTarget(1.0, 0.5, 0.15),
        "spectral_flux_std": FeatureTarget(2.0, 8.0, 4.0),
        "energy_std": FeatureTarget(2.0, 0.25, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 2500.0, 1000.0),
        "crest_factor_db": FeatureTarget(1.0, 12.0, 4.0),
        "energy_highmid": FeatureTarget(1.0, 0.18, 0.08),
        "danceability": FeatureTarget(1.5, 2.0, 0.4),
        "dissonance_mean": FeatureTarget(1.0, 0.3, 0.15),
        "dynamic_complexity": FeatureTarget(2.0, 0.7, 0.15),
        "pitch_salience_mean": FeatureTarget(1.0, 0.2, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 12.0, 5.0),
        "bpm_stability": FeatureTarget(2.0, 0.7, 0.1),
        "pulse_clarity": FeatureTarget(1.0, 0.5, 0.2),
        "onset_rate": FeatureTarget(2.0, 6.0, 2.0),
        "kick_prominence": FeatureTarget(1.0, 0.6, 0.2),
        "bpm": FeatureTarget(1.5, 128.0, 8.0),
    },
)

PEAK_TIME = SubgenreProfile(
    subgenre=TechnoSubgenre.PEAK_TIME,
    features={
        "energy_mean": FeatureTarget(2.0, 0.7, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 3000.0, 1000.0),
        "energy_low": FeatureTarget(1.5, 0.25, 0.1),
        "crest_factor_db": FeatureTarget(1.0, 6.0, 3.0),
        "spectral_flux_mean": FeatureTarget(1.0, 10.0, 5.0),
        "loudness_range_lu": FeatureTarget(1.0, 5.0, 3.0),
        "danceability": FeatureTarget(2.0, 2.8, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.35, 0.15),
        "dynamic_complexity": FeatureTarget(1.0, 0.35, 0.15),
        "pitch_salience_mean": FeatureTarget(1.0, 0.12, 0.08),
        "spectral_complexity_mean": FeatureTarget(1.0, 15.0, 5.0),
        "bpm_stability": FeatureTarget(1.5, 0.9, 0.05),
        "hp_ratio": FeatureTarget(1.0, 1.2, 0.3),
        "pulse_clarity": FeatureTarget(1.5, 0.7, 0.15),
        "kick_prominence": FeatureTarget(2.0, 0.85, 0.1),
        "onset_rate": FeatureTarget(1.0, 4.5, 1.5),
    },
)

ACID = SubgenreProfile(
    subgenre=TechnoSubgenre.ACID,
    features={
        "spectral_centroid_hz": FeatureTarget(2.5, 4000.0, 1500.0),
        "spectral_flatness": FeatureTarget(1.5, 0.25, 0.1),
        "energy_mean": FeatureTarget(1.0, 0.55, 0.15),
        "energy_highmid": FeatureTarget(1.5, 0.22, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 8.0, 4.0),
        "spectral_rolloff_85": FeatureTarget(1.0, 5000.0, 2000.0),
        "danceability": FeatureTarget(1.5, 2.2, 0.4),
        "dissonance_mean": FeatureTarget(2.0, 0.6, 0.15),
        "dynamic_complexity": FeatureTarget(1.0, 0.4, 0.2),
        "pitch_salience_mean": FeatureTarget(1.5, 0.35, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.5, 18.0, 5.0),
        "spectral_contrast": FeatureTarget(1.5, 22.0, 5.0),
    },
)

RAW = SubgenreProfile(
    subgenre=TechnoSubgenre.RAW,
    features={
        "energy_mean": FeatureTarget(1.5, 0.65, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 3500.0, 1200.0),
        "spectral_flatness": FeatureTarget(1.5, 0.3, 0.12),
        "crest_factor_db": FeatureTarget(1.0, 5.0, 3.0),
        "loudness_range_lu": FeatureTarget(1.0, 4.0, 2.0),
        "spectral_flux_std": FeatureTarget(1.0, 5.0, 3.0),
        "danceability": FeatureTarget(1.0, 2.3, 0.4),
        "dissonance_mean": FeatureTarget(1.5, 0.5, 0.15),
        "dynamic_complexity": FeatureTarget(1.5, 0.45, 0.2),
        "pitch_salience_mean": FeatureTarget(1.0, 0.12, 0.08),
        "spectral_complexity_mean": FeatureTarget(1.5, 18.0, 5.0),
        "hp_ratio": FeatureTarget(1.0, 1.1, 0.3),
    },
)

INDUSTRIAL = SubgenreProfile(
    subgenre=TechnoSubgenre.INDUSTRIAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.75, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 4000.0, 1500.0),
        "spectral_flatness": FeatureTarget(2.0, 0.35, 0.12),
        "loudness_range_lu": FeatureTarget(1.5, 3.0, 2.0),
        "crest_factor_db": FeatureTarget(1.0, 4.0, 2.0),
        "energy_high": FeatureTarget(1.0, 0.15, 0.08),
        "danceability": FeatureTarget(1.0, 2.0, 0.5),
        "dissonance_mean": FeatureTarget(2.0, 0.55, 0.15),
        "dynamic_complexity": FeatureTarget(1.5, 0.5, 0.2),
        "pitch_salience_mean": FeatureTarget(1.0, 0.1, 0.08),
        "spectral_complexity_mean": FeatureTarget(2.0, 22.0, 5.0),
        "hp_ratio": FeatureTarget(1.0, 1.0, 0.3),
        "kick_prominence": FeatureTarget(1.5, 0.7, 0.2),
        "onset_rate": FeatureTarget(1.0, 5.0, 2.0),
    },
)

HARD_TECHNO = SubgenreProfile(
    subgenre=TechnoSubgenre.HARD_TECHNO,
    features={
        "energy_mean": FeatureTarget(2.0, 0.85, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 3500.0, 1500.0),
        "energy_low": FeatureTarget(1.5, 0.3, 0.12),
        "crest_factor_db": FeatureTarget(1.0, 3.0, 2.0),
        "loudness_range_lu": FeatureTarget(1.0, 3.0, 2.0),
        "spectral_flux_mean": FeatureTarget(1.0, 12.0, 5.0),
        "danceability": FeatureTarget(1.5, 2.6, 0.3),
        "dissonance_mean": FeatureTarget(1.5, 0.45, 0.15),
        "dynamic_complexity": FeatureTarget(1.0, 0.3, 0.15),
        "pitch_salience_mean": FeatureTarget(1.0, 0.1, 0.08),
        "spectral_complexity_mean": FeatureTarget(1.5, 18.0, 5.0),
        "bpm_stability": FeatureTarget(1.0, 0.9, 0.05),
        "hp_ratio": FeatureTarget(1.0, 1.1, 0.3),
        "pulse_clarity": FeatureTarget(1.5, 0.7, 0.15),
        "kick_prominence": FeatureTarget(1.5, 0.8, 0.15),
        "integrated_lufs": FeatureTarget(1.5, -6.0, 2.0),
        "bpm": FeatureTarget(1.5, 145.0, 5.0),
    },
)

ALL_PROFILES: tuple[SubgenreProfile, ...] = (
    AMBIENT_DUB,
    DUB_TECHNO,
    MINIMAL,
    DETROIT,
    MELODIC_DEEP,
    PROGRESSIVE,
    HYPNOTIC,
    DRIVING,
    TRIBAL,
    BREAKBEAT,
    PEAK_TIME,
    ACID,
    RAW,
    INDUSTRIAL,
    HARD_TECHNO,
)

# Catch-all subgenres identified by non-zero penalty in profile
CATCH_ALL_SUBGENRES: frozenset[TechnoSubgenre] = frozenset(
    p.subgenre for p in ALL_PROFILES if p.catch_all_penalty > 0
)
