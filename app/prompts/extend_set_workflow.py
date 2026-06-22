"""extend_set_workflow — lengthen an existing set while preserving its arc."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int, add_tracks: int, where: str) -> str:
    return f"""Extend set {set_id} by ~{add_tracks} tracks at the '{where}' end
without breaking its energy arc.

1. Read the current shape:
   local://sets/{set_id}/tracks    — ordered ids; note head and tail tracks.
   local://sets/{set_id}/narrative — current arc and where it sits on the
   energy axis at the head ('{where}'=start) or tail ('{where}'=end).

2. Decide the energy direction the extension must continue:
   - 'end'   -> usually keep climbing toward / holding the peak, or begin the
                cool-down if the set already peaked.
   - 'start' -> prepend a gentler warm-up ramp INTO the existing opener.
   session://energy-trend — adaptive hint for the next energy step.

3. Source candidates that flow from the boundary track:
   local://tracks/<boundary_track_id>/suggest_next?limit={max(add_tracks * 3, 15)}
   — add &energy_direction=<up|down|flat> to bias the candidates.
   — at 'end' seed from the tail track; at 'start' build backwards into the
     head track (candidate -> head must mix).

4. Keep only viable, on-character candidates:
   - exclude tracks already in the set and banned tracks
     (entity_list(entity="track_feedback", filters={{"status": "banned"}})).
   - ensure level >= 3:
     entity_list(entity="track_features", filters={{"track_id__in": [...]}},
                fields="scoring").

5. Re-order the COMBINED list (existing + additions) so the seam is smooth,
   pinning the existing tracks so the GA does not reshuffle the approved body:
   sequence_optimize(track_ids=[<existing + new>], algorithm="ga",
                    pinned=[<existing ids>])

6. Persist and verify the seam:
   entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [...], "label": "extend_{where}"}})
   local://sets/{set_id}/review — the new boundary transitions must clear
   hard_reject; local://sets/{set_id}/narrative — arc still coherent.

Return: {{"set_id": {set_id}, "added": N, "where": "{where}",
         "new_version_id": ..., "quality_score": ...}}.
"""


@prompt(
    name="extend_set_workflow",
    description="Lengthen an existing set at the start or end while preserving the energy arc.",
    tags={"namespace:workflow", "set_building"},
    meta=PROMPT_META,
)
def extend_set_workflow(set_id: int, add_tracks: int = 5, where: str = "end") -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, add_tracks, where))],
        description=f"Extend set {set_id} by {add_tracks} tracks at '{where}'.",
    )
