"""DEPRECATED: Use ``app.domain.render.stem_timbre`` instead.

This module is a transitional shim kept for one release. New code should
import from ``stem_timbre``.
"""

from __future__ import annotations

import warnings

from app.domain.render.stem_timbre import STEM_TIMBRE, StemTimbre, stem_timbre

__all__ = ["STEM_VOICING", "StemVoicing", "stem_voicing"]  # noqa: F822 — dynamic via __getattr__


def __getattr__(name: str):
    if name == "STEM_VOICING":
        warnings.warn(
            "STEM_VOICING is deprecated, use STEM_TIMBRE from app.domain.render.stem_timbre",
            DeprecationWarning,
            stacklevel=2,
        )
        return STEM_TIMBRE
    if name == "StemVoicing":
        warnings.warn(
            "StemVoicing is deprecated, use StemTimbre from app.domain.render.stem_timbre",
            DeprecationWarning,
            stacklevel=2,
        )
        return StemTimbre
    if name == "stem_voicing":
        warnings.warn(
            "stem_voicing() is deprecated, use stem_timbre() from app.domain.render.stem_timbre",
            DeprecationWarning,
            stacklevel=2,
        )
        return stem_timbre
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
