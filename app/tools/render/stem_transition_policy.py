"""MCP tool: dj_stem_transition_policy.

Set stem transition policy defaults for the next render. None = keep default.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context
from fastmcp.tools import tool

# In-memory session state for stem policy overrides. Per-session only.
# Per the design doc §10: default to in-memory only (simpler).
_SESSION_STEM_POLICY: dict[str, Any] = {}


def get_session_stem_policy() -> dict[str, Any]:
    """Return the current session stem policy overrides."""
    return dict(_SESSION_STEM_POLICY)


def clear_session_stem_policy() -> None:
    """Clear all session stem policy overrides."""
    _SESSION_STEM_POLICY.clear()


def merge_session_stem_policy(kwargs: dict[str, Any] | None) -> dict[str, Any]:
    """Merge one-shot kwargs into the session policy and return the merged view.

    Used by ``dj_render_mixdown`` when no per-render kwargs are passed.
    """
    if not kwargs:
        return get_session_stem_policy()
    merged = get_session_stem_policy()
    for key, value in kwargs.items():
        if value is not None:
            merged[key] = value
    return merged


@tool(name="dj_stem_transition_policy", tags={"namespace:render:config"})
async def stem_transition_policy(
    ctx: Context,
    vocals_swap_ratio: float | None = None,
    harmonic_swap_ratio: float | None = None,
    percussion_swap_ratio: float | None = None,
    bass_pinpoint_beats: float | None = None,
    hpf_overrides: dict[str, int] | None = None,
    gain_offsets_db: dict[str, float] | None = None,
    fade_curves: dict[str, str] | None = None,
    energy_match_db_window: float | None = None,
    phrase_alignment: bool | None = None,
    phrase_snap_window_bars: int | None = None,
    vocal_clash_aggression: float | None = None,
    transition_length_multiplier: float | None = None,
    subgenre: str | None = None,
) -> dict[str, Any]:
    """Set stem transition policy defaults for the next render. None = keep default.

    Args:
        vocals_swap_ratio: Ratio (0-1) at which to swap vocals.
        harmonic_swap_ratio: Ratio (0-1) at which to swap harmonic content.
        percussion_swap_ratio: Ratio (0-1) at which to swap percussion.
        bass_pinpoint_beats: Pinpoint swap window length in beats.
        hpf_overrides: Per-stem HPF overrides in Hz (vocals, drums, bass, harmonic, percussion).
        gain_offsets_db: Per-stem gain offsets in dB.
        fade_curves: Per-stem fade curve names (qsin, tri, exp, log, squ, sin).
        energy_match_db_window: Energy matching window in dB.
        phrase_alignment: Enable phrase alignment of pinpoint swaps.
        phrase_snap_window_bars: Max bars to snap to phrase boundary.
        vocal_clash_aggression: 0-1, how aggressively to fade vocals on clash.
        transition_length_multiplier: Multiplier for transition length.
        subgenre: Subgenre preset name (overrides current).
    """
    updates: dict[str, Any] = {}
    for key, value in {
        "vocals_swap_ratio": vocals_swap_ratio,
        "harmonic_swap_ratio": harmonic_swap_ratio,
        "percussion_swap_ratio": percussion_swap_ratio,
        "bass_pinpoint_beats": bass_pinpoint_beats,
        "hpf_overrides": hpf_overrides,
        "gain_offsets_db": gain_offsets_db,
        "fade_curves": fade_curves,
        "energy_match_db_window": energy_match_db_window,
        "phrase_alignment": phrase_alignment,
        "phrase_snap_window_bars": phrase_snap_window_bars,
        "vocal_clash_aggression": vocal_clash_aggression,
        "transition_length_multiplier": transition_length_multiplier,
        "subgenre": subgenre,
    }.items():
        if value is not None:
            updates[key] = value

    _SESSION_STEM_POLICY.update(updates)
    return {
        "applied": list(updates.keys()),
        "policy": _SESSION_STEM_POLICY,
    }


__all__ = [
    "clear_session_stem_policy",
    "get_session_stem_policy",
    "merge_session_stem_policy",
    "stem_transition_policy",
]
