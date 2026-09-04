"""Legacy/new transition parity diagnostics."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    technical_parity: bool
    score_delta: float
    legacy_candidate: str = ""
    new_candidate: str = ""
    recipe_parity: bool = True
    rejection_parity: bool = True
    technical_margin_delta: float = 0.0
    dimension_deltas: tuple[tuple[str, float], ...] = ()

    @classmethod
    def compare(
        cls,
        legacy_candidate: str,
        new_candidate: str,
        legacy_score: float,
        new_score: float,
        *,
        legacy_recipe: str | None = None,
        new_recipe: str | None = None,
        legacy_rejected: Sequence[str] = (),
        new_rejected: Sequence[str] = (),
        legacy_accepted: bool = True,
        new_accepted: bool = True,
        legacy_technical_margin: float = 0.0,
        new_technical_margin: float = 0.0,
        legacy_dimensions: Mapping[str, float] | None = None,
        new_dimensions: Mapping[str, float] | None = None,
    ) -> ShadowComparison:
        legacy_values = legacy_dimensions or {}
        new_values = new_dimensions or {}
        names = sorted(set(legacy_values) | set(new_values))
        deltas = tuple(
            (name, round(new_values.get(name, 0.0) - legacy_values.get(name, 0.0), 12))
            for name in names
        )
        recipe_parity = True
        if legacy_recipe is not None or new_recipe is not None:
            recipe_parity = legacy_recipe == new_recipe
        return cls(
            legacy_accepted == new_accepted,
            round(new_score - legacy_score, 12),
            legacy_candidate,
            new_candidate,
            recipe_parity,
            tuple(legacy_rejected) == tuple(new_rejected),
            round(new_technical_margin - legacy_technical_margin, 12),
            deltas,
        )


@dataclass(frozen=True, slots=True)
class ShadowComparisonRecord:
    """Persistable, deterministic record of one legacy/new comparison."""

    execution_identity: str
    comparison: ShadowComparison

    @property
    def identity(self) -> str:
        payload = self.canonical_payload()
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def canonical_payload(self) -> dict[str, object]:
        return {
            "execution_identity": self.execution_identity,
            "comparison": asdict(self.comparison),
        }

    @classmethod
    def create(
        cls, execution_identity: str, comparison: ShadowComparison
    ) -> ShadowComparisonRecord:
        return cls(execution_identity=execution_identity, comparison=comparison)
