"""stem_matrix — 12-deck stem activation matrix over set timeline."""
from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.stem_matrix import ActiveStem, MatrixFrame, StemMatrixResult
from app.server.di import get_uow

STEM_TYPES = ("acappella", "bass", "drums", "harmonic", "instrumental")


@tool(
    name="stem_matrix",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a 12-deck stem activation matrix over the set timeline. "
        "Shows which stems (acappella/bass/drums/harmonic/instrumental) from "
        "which tracks are active at each time point. Used for multi-deck "
        "layering and stem-aware rendering."
    ),
    meta={"timeout_s": 15.0},
    timeout=15.0,
)
async def stem_matrix(
    track_order: Annotated[
        list[int], Field(min_length=2, max_length=30, description="Ordered track IDs")
    ],
    target_bpm: Annotated[
        float, Field(ge=60, le=200, description="Target BPM")
    ] = 130.0,
    transition_bars: Annotated[
        int, Field(ge=4, le=128, description="Transition length in bars")
    ] = 32,
    body_bars: Annotated[
        int, Field(ge=4, le=128, description="Per-track body length in bars")
    ] = 32,
    uow: UnitOfWork = Depends(get_uow),
) -> StemMatrixResult:
    bar_s = 4.0 * (60.0 / target_bpm)
    body_s = body_bars * bar_s
    trans_s = transition_bars * bar_s
    frame_interval = bar_s / 4.0  # 1 beat

    frames: list[MatrixFrame] = []
    t = 0.0
    for i, tid in enumerate(track_order):
        # Body frames
        body_end = t + body_s
        while t < body_end:
            frames.append(MatrixFrame(
                time_s=round(t, 2),
                active_decks=[
                    ActiveStem(deck_index=j, stem_type=st, track_id=tid)
                    for j, st in enumerate(STEM_TYPES)
                ],
                fade_outs=0, fade_ins=0,
            ))
            t += frame_interval

        # Transition frames
        if i < len(track_order) - 1:
            next_tid = track_order[i + 1]
            trans_end = t + trans_s
            while t < trans_end:
                progress = (t - (trans_end - trans_s)) / trans_s
                fade_outs = 3 if progress > 0.5 else 0
                fade_ins = 3 if progress > 0.3 else 0
                frames.append(MatrixFrame(
                    time_s=round(t, 2),
                    active_decks=[
                        ActiveStem(deck_index=j, stem_type=st, track_id=tid)
                        for j, st in enumerate(STEM_TYPES[:3])
                    ] + [
                        ActiveStem(deck_index=j + 5, stem_type=st, track_id=next_tid)
                        for j, st in enumerate(STEM_TYPES[:3])
                    ],
                    fade_outs=fade_outs, fade_ins=fade_ins,
                ))
                t += frame_interval

    return StemMatrixResult(
        total_duration_s=t,
        frame_count=len(frames),
        target_bpm=target_bpm,
        frames=frames,
    )
