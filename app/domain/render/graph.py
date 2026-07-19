"""Public entry point for the classic filtergraph (Facade over the builder).

The construction logic lives in :class:`~app.domain.render.filtergraph.ClassicGraphBuilder`;
this keeps the historical ``build_filtergraph(plan)`` call site stable.
"""

from __future__ import annotations

from app.domain.render.filtergraph import ClassicGraphBuilder
from app.domain.render.models import RenderPlan

_BUILDER = ClassicGraphBuilder()


def build_filtergraph(plan: RenderPlan) -> list[str]:
    """Classic single-file-per-track 3-band EQ bass-swap filtergraph."""
    return _BUILDER.build(plan)
