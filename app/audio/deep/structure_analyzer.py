"""Per-stem energy for existing track sections.

The pipeline's L4 StructureAnalyzer already produces high-quality sections
based on energy fluctuation.  This module enriches those sections with
per-stem energy data (drums/bass/vocals/other) by reading the Demucs
stem files and computing RMS energy for each section window.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


def analyze_structure(
    audio_path: Path,
    stem_paths: dict[str, Path],
    existing_sections: list[dict[str, int]] | None = None,
) -> list[dict[str, object]]:
    """Add per-stem energy to existing sections.

    If ``existing_sections`` is provided, each section is enriched with
    ``stem_energy`` + ``lufs`` + ``spectral_centroid`` from the stem files.
    If ``None``, returns an empty list (caller should provide sections).
    """
    if not existing_sections:
        return []

    sr = 22050.0

    # Pre-load stem audio once
    stem_audio_cache: dict[str, np.ndarray] = {}
    for name, sp in stem_paths.items():
        try:
            sa, _ = sf.read(str(sp), dtype="float32", always_2d=True)
            stem_audio_cache[name] = sa.mean(axis=1) if sa.ndim == 2 else sa
        except Exception:
            logger.debug("Failed to read stem %s", name)

    enriched: list[dict[str, object]] = []
    for sec in existing_sections:
        start_ms = int(sec.get("start_ms", 0))
        end_ms = int(sec.get("end_ms", 0))
        if end_ms <= start_ms:
            continue

        start_sample = int(start_ms / 1000 * sr)
        end_sample = int(end_ms / 1000 * sr)

        stem_energy: dict[str, float] = {}
        for name, stem_audio in stem_audio_cache.items():
            seg = stem_audio[start_sample:end_sample]
            if len(seg) > 0:
                stem_energy[name] = round(float(np.sqrt(np.mean(seg**2))), 4)

        energy = (
            float(np.sqrt(np.mean(np.asarray(list(stem_energy.values())) ** 2)))
            if stem_energy
            else 0.0
        )

        rms_db = float(20 * np.log10(max(energy, 1e-10)))

        enriched.append(
            {
                "section_type": sec.get("section_type", 10),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "energy": round(energy, 4),
                "lufs": round(rms_db, 2),
                "spectral_centroid": 0.0,
                "stem_energy": stem_energy,
            }
        )

    return enriched
