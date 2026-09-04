"""Reproducibility identity for analysis, planning and rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    source_hash: str
    config_hash: str
    engine_version: str
    analysis_version: str
    model_version: str
    dsp_version: str
    renderer_version: str
    seed: int

    @property
    def hash(self) -> str:
        payload = {field.name: getattr(self, field.name) for field in fields(self)}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
