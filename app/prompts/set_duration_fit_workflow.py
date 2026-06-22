"""set_duration_fit_workflow — fit a set to an exact time slot (trim/extend)."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int, target_minutes: int) -> str:
    target_ms = target_minutes * 60_000
    return f"""Fit set {set_id} to a {target_minutes}-minute slot
(~{target_ms} ms) without breaking its energy arc — the festival/club reality
where the slot length is fixed, not negotiable.

The engine does NOT enforce duration as a hard constraint (templates carry
advisory per-slot targets only), so this is a deliberate trim/extend pass.

1. Measure the current length:
   local://sets/{set_id}/tracks  — ordered (position, track_id, title).
   Sum the track durations:
   entity_aggregate(entity="track", operation="sum", field="duration_ms",
                    filters={{"id__in": [<set track ids>]}})
   — compare the sum to the target {target_ms} ms. Account for blend overlap:
     each transition's transition_bars trims a few seconds of real wall-clock
     (read entity_list(entity="transition", filters={{"from_track_id__in":
     [...]}}, fields="summary") if you need the exact overlap_ms per pair).

2. If the set is TOO LONG (sum > target by more than ~one track):
   - Identify the weakest / most droppable slots: read
     local://sets/{set_id}/review and prefer cutting tracks adjacent to a weak
     transition (removing them also fixes a seam).
   - Cut from the MIDDLE plateau, never the warm-up opener or the peak/closer —
     those carry the arc. Re-run replace_track_workflow if a cut leaves a hole.

3. If the set is TOO SHORT (sum < target by more than ~one track):
   - Run the extend_set_workflow prompt to add tracks at the 'end' (or 'start'
     for a longer warm-up) until the sum reaches the target.

4. Re-order the adjusted track list so the seams stay smooth, pinning the
   opener and closer so the arc shape survives the resize:
   sequence_optimize(track_ids=[<adjusted ids>], algorithm="ga",
                    pinned=[<opener_id>, <closer_id>])

5. Persist + verify length AND arc:
   entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [...], "label": "fit_{target_minutes}m"}})
   entity_aggregate(entity="track", operation="sum", field="duration_ms",
                    filters={{"id__in": [<new ids>]}})  — within ~1 track of target.
   local://sets/{set_id}/narrative — arc still reads as intended after resize.
   local://sets/{set_id}/review    — no new hard conflicts introduced.

6. Report the fit: how many tracks added/removed and the final duration vs the
   {target_minutes}-minute target (note it is wall-clock-approximate; real
   length shifts a little with live blend lengths).

Return: {{"set_id": {set_id}, "target_minutes": {target_minutes},
         "added": N, "removed": N, "final_duration_ms": ...,
         "new_version_id": ...}}.
"""


@prompt(
    name="set_duration_fit_workflow",
    description="Trim/extend a set to fit an exact time slot while preserving its energy arc.",
    tags={"namespace:workflow", "delivery", "set_building"},
    meta=PROMPT_META,
)
def set_duration_fit_workflow(set_id: int, target_minutes: int = 60) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, target_minutes))],
        description=f"Fit set {set_id} to a {target_minutes}-minute slot.",
    )
