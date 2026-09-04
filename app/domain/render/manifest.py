"""Canonical render manifest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class RenderManifest:
    plan_identity: str
    config_identity: str
    source_identity: str
    renderer_version: str
    dsp_version: str
    model_version: str

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def identity(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
