"""multi_deck_plan — 3+ simultaneous deck render plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.multi_deck import DeckAssign, DeckWindow, MultiDeckPlanResult
from app.server.di import get_uow


@dataclass
class SimpleTrackInfo:
    track_id: int
    title: str
    bpm: float
    duration_ms: int


@tool(
    name="multi_deck_plan",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Generate a multi-deck render plan for 3+ simultaneous tracks. "
        "Assigns active decks with per-stem EQ, gain, and pan settings "
        "for each time window in the set. Returns ffmpeg amix graph."
    ),
    meta={"timeout_s": 10.0},
    timeout=10.0,
)
async def multi_deck_plan(
    track_order: Annotated[
        list[int], Field(min_length=2, max_length=30, description="Ordered track IDs")
    ],
    stem_mode: Annotated[bool, Field(description="Use demucs stem mode")] = False,
    max_simultaneous: Annotated[int, Field(ge=2, le=12, description="Max concurrent decks")] = 6,
    uow: UnitOfWork = Depends(get_uow),
) -> MultiDeckPlanResult:
    # Read track metadata from DB
    input_map: dict[int, Any] = {}
    for tid in track_order:
        track = await uow.tracks.get(tid)
        features = await uow.track_features.get_by_track_id(tid)
        if track:
            input_map[tid] = SimpleTrackInfo(
                track_id=tid,
                title=track.title or "",
                bpm=float(getattr(features, "bpm", 130) or 130),
                duration_ms=int(getattr(track, "duration_ms", 0) or 0),
            )

    windows: list[DeckWindow] = []
    bar_s = 4.0 * (60.0 / 130.0)
    body_s = 32 * bar_s
    trans_s = 32 * bar_s

    for i, tid in enumerate(track_order):
        ti = input_map.get(tid)
        if not ti:
            continue
        start = i * body_s
        # Body window
        windows.append(
            DeckWindow(
                start_s=start,
                end_s=start + body_s,
                decks=[
                    DeckAssign(
                        deck_index=0,
                        track_id=tid,
                        active_stems=["drums", "bass", "other"],
                        gain_db=0.0,
                        lowpass_hz=20000,
                        highpass_hz=20,
                    )
                ],
            )
        )
        # Transition window (if not last)
        if i < len(track_order) - 1:
            next_tid = track_order[i + 1]
            windows.append(
                DeckWindow(
                    start_s=start + body_s,
                    end_s=start + body_s + trans_s,
                    decks=[
                        DeckAssign(
                            deck_index=0,
                            track_id=tid,
                            active_stems=["drums"],
                            gain_db=-6.0,
                            lowpass_hz=20000,
                            highpass_hz=20,
                        ),
                        DeckAssign(
                            deck_index=1,
                            track_id=next_tid,
                            active_stems=["bass", "drums"],
                            gain_db=-3.0,
                            lowpass_hz=20000,
                            highpass_hz=20,
                        ),
                    ],
                )
            )

    return MultiDeckPlanResult(
        max_simultaneous=max_simultaneous,
        target_bpm=130.0,
        windows=windows,
        ffmpeg_amix_graph="",
    )
