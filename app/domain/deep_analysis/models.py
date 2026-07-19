from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class L6AnalysisResult:
    track_id: int
    level: int = 6
    stems: dict[str, str] = field(default_factory=dict)
    stem_features_count: int = 0
    beatgrid_registered: bool = False
    embeddings_count: int = 0
    sections_count: int = 0
    cross_similarity_computed: bool = False
    timeseries_uploaded: bool = False
    waveform_uploaded: bool = False
    errors: list[str] = field(default_factory=list)
    drum_bands: dict[str, Any] = field(default_factory=dict)
