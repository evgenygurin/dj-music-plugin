"""Immutable transition execution contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recipes import TransitionRecipe


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    source_id: str
    target_id: str
    duration_bars: int
    effective_bpm: float
    recipe: TransitionRecipe
    plan_version: str = "1"
    engine_version: str = "universal-1"
    config_identity: str = ""
    source_analysis_identity: str = ""
    target_analysis_identity: str = ""
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        source_id: str,
        target_id: str,
        duration_bars: int,
        effective_bpm: float,
        recipe: TransitionRecipe,
        *,
        engine_version: str = "universal-1",
        config_identity: str = "",
        source_analysis_identity: str = "",
        target_analysis_identity: str = "",
        diagnostics: tuple[str, ...] = (),
    ) -> TransitionPlan:
        return cls(
            source_id,
            target_id,
            duration_bars,
            effective_bpm,
            recipe,
            engine_version=engine_version,
            config_identity=config_identity,
            source_analysis_identity=source_analysis_identity,
            target_analysis_identity=target_analysis_identity,
            diagnostics=diagnostics,
        )

    def canonical_json(self) -> str:
        payload = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "duration_bars": self.duration_bars,
            "effective_bpm": self.effective_bpm,
            "recipe": {
                "kind": self.recipe.kind.value,
                "bars": self.recipe.bars,
                "parameters": self.recipe.parameters,
            },
            "plan_version": self.plan_version,
            "engine_version": self.engine_version,
            "config_identity": self.config_identity,
            "source_analysis_identity": self.source_analysis_identity,
            "target_analysis_identity": self.target_analysis_identity,
            "diagnostics": self.diagnostics,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @property
    def execution_identity(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
