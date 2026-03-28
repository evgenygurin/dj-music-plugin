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
