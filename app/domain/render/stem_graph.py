"""Public entry point for the stem filtergraph (Facade over the builder).

The construction logic lives in :class:`~app.domain.render.filtergraph.StemGraphBuilder`;
this keeps the historical ``build_stem_filtergraph(plan)`` call site stable.
"""

from __future__ import annotations

from app.domain.render.filtergraph import StemGraphBuilder
from app.domain.render.models import RenderPlan

_BUILDER = StemGraphBuilder()


def build_stem_filtergraph(plan: RenderPlan) -> list[str]:
    """Stem multi-deck filtergraph — 4 demucs stems per track, staggered fades."""
    return _BUILDER.build(plan)
