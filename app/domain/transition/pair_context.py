"""Compatibility exports for the shared transition pair context."""

from __future__ import annotations

from app.domain.transition.section_context import (
    TransitionPairContext,
    build_pair_context,
)

__all__ = ["TransitionPairContext", "build_pair_context"]
