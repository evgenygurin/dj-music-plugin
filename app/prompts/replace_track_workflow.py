"""replace_track_workflow — swap a weak slot in a set with a better candidate."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int, position: int) -> str:
    return f"""Replace the track at position {position} in set {set_id}.

1. Establish context:
   local://sets/{set_id}/tracks — confirm the current track_id at position
   {position} and its neighbours at {position}-1 and {position}+1.
   local://sets/{set_id}/review — confirm WHY this slot is weak (incoming
   and/or outgoing transition flagged).

2. Get ranked replacements that respect both neighbours and the slot's
   target energy/mood:
   local://tracks/<incoming_neighbour_id>/suggest_replacement/{set_id}/{position}
   — returns candidates scored for fit at this exact slot (considers the
     surrounding transitions and the template arc).

3. Filter the candidates:
   - drop anything on the ban list:
     entity_list(entity="track_feedback", filters={{"status": "banned"}})
   - prefer tracks already analyzed to level >= 3 (no analysis stall):
     entity_list(entity="track_features", filters={{"track_id__in": [...]}},
                fields="scoring")

4. Validate the top candidate against BOTH adjacent transitions:
   local://transition/<prev_id>/<candidate_id>/score
   local://transition/<candidate_id>/<next_id>/score
   — both overall should beat the original slot's transitions and clear
     hard_reject.

5. Apply by persisting a new version with the swapped order:
   entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [<order with candidate at position {position}>],
                "label": "swap_p{position}"}})

6. Confirm improvement:
   local://sets/{set_id}/versions/compare/<old>/<new> — quality_score up,
   no new hard conflicts.

If no candidate beats the incumbent on both sides, leave the slot and instead
run fix_transition_workflow on the weaker adjacent pair.

Return: {{"set_id": {set_id}, "position": {position}, "old_track": ...,
         "new_track": ..., "score_delta": ..., "new_version_id": ...}}.
"""


@prompt(
    name="replace_track_workflow",
    description="Swap a weak track slot in a set with a better-fitting candidate.",
    tags={"namespace:workflow", "set_building", "reasoning"},
    meta=PROMPT_META,
)
def replace_track_workflow(set_id: int, position: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, position))],
        description=f"Replace track at position {position} in set {set_id}.",
    )
