"""Canonical execution manifest for reproducible renders."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ExecutionManifest:
    source_hash: str
    config_hash: str
    engine_version: str
    analysis_version: str
    model_version: str
    dsp_version: str
    renderer_version: str
    seed: int

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
