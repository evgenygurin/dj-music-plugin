"""Policy builder factory (§4.1 builder.py)."""

from __future__ import annotations

from app.domain.render.stem_policy.base import CompositeStemTransitionPolicy, default_policy
from app.domain.render.stem_policy.models import AvailableData

__all__ = ["AvailableData", "CompositeStemTransitionPolicy", "default_policy"]


def build_default_policy(available: AvailableData | None = None) -> CompositeStemTransitionPolicy:
    """Convenience wrapper used by plan_assembler / filtergraph."""
    return default_policy(available or AvailableData())
