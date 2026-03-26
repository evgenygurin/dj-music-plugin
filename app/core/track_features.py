"""TrackFeatures dataclass — minimal feature set for transition scoring.

Lives in core layer so repositories can import it without depending on services.
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
        energy_bands = bands_raw if all(b is not None for b in bands_raw) else None

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
        )
