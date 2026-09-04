"""Immutable, versioned analysis snapshot and deterministic identity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from .beatgrid import BeatGrid
from .cue import CuePoint
from .phrase import Phrase
from .structure import Section
from .tempo import TempoHypothesis


def _pairs(values: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in values.items()))


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """Reusable analysis result whose identity includes all invalidators."""

    source_hash: str
    schema_version: str
    analyzer_versions: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    engine_version: str = "universal-1"
    model_versions: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    dsp_backend: str = "unknown"
    analysis_config_hash: str = ""
    tempo_hypotheses: tuple[TempoHypothesis, ...] = field(default_factory=tuple)
    beatgrid: BeatGrid | None = None
    phrases: tuple[Phrase, ...] = field(default_factory=tuple)
    sections: tuple[Section, ...] = field(default_factory=tuple)
    cues: tuple[CuePoint, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.source_hash.strip():
            raise ValueError("source_hash must not be empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        object.__setattr__(self, "analyzer_versions", _pairs(dict(self.analyzer_versions)))
        object.__setattr__(self, "model_versions", _pairs(dict(self.model_versions)))

    @property
    def identity_hash(self) -> str:
        """Return a stable SHA-256 identity for cache invalidation."""
        payload = {
            "source_hash": self.source_hash,
            "schema_version": self.schema_version,
            "analyzer_versions": self.analyzer_versions,
            "engine_version": self.engine_version,
            "model_versions": self.model_versions,
            "dsp_backend": self.dsp_backend,
            "analysis_config_hash": self.analysis_config_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
