"""rescue_set_workflow — repair a set riddled with hard-reject transitions."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int) -> str:
    return f"""Triage set {set_id} when it is full of hard conflicts (multiple
hard_reject transitions) and rescue it into a playable set.

This is the heavy-repair sibling of set_review_workflow (critique) and
fix_transition_workflow (one pair). Here many pairs fail, so reorder FIRST
before touching individual tracks — most hard_rejects are an ordering problem,
not a track problem.

1. Measure the damage:
   local://sets/{set_id}/review — count hard_reject pairs and weak
   (overall < 0.5) transitions; note their positions.
   dj_entity_list(entity="transition",
              filters={{"from_track_id__in": [<set track ids>], "hard_reject": true}},
              fields="summary")
   — reject_reason tells you the dominant failure (bpm cliff / camelot clash /
     energy gap). If one reason dominates, the cure is structural.

2. Cheapest fix — RE-ORDER the existing tracks (no swaps yet):
   dj_sequence_optimize(track_ids=[<current set ids>], algorithm="ga",
                    template=<set template>)
   — the GA threads a path that avoids hard_reject steps if one exists. Persist
     a trial version and re-check:
   dj_entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [...], "label": "rescue_reorder"}})
   local://sets/{set_id}/review — how many conflicts survived the reorder?

3. Isolate the IRREDEEMABLE tracks. A track that hard_rejects against most of
   the pool is a foreign-character intruder (wrong BPM band, lone key, or
   energy outlier). Find it:
   dj_entity_list(entity="track_features", filters={{"track_id__in": [...]}},
              fields="scoring")
   — the BPM/key/mood outlier is usually the culprit. Drop it from the set or
     replace it via replace_track_workflow for its slot.

4. For the FEW conflicts left after reorder + cull, bridge them:
   - run fix_transition_workflow on each remaining hard pair (technique ->
     bridge track -> replace).
   - the engine's safety net for an unavoidable hard pair is ECHO_OUT (echo
     tail masks the clash); accept it only where no clean fix exists.

5. Re-persist the rescued order and confirm recovery:
   dj_entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [...], "label": "rescue_final"}})
   local://sets/{set_id}/versions/compare/<broken>/<rescued> — hard_reject
   count must drop to 0 (or only intentional ECHO_OUT bridges remain).
   local://sets/{set_id}/narrative — the arc must still read coherently.

6. If the set CANNOT be rescued (the pool is genuinely incoherent — three
   disjoint BPM bands), say so plainly and recommend splitting it into two
   sets or sourcing bridge tracks via crate_digging_workflow.

Return: {{"set_id": {set_id}, "hard_before": N, "hard_after": N,
         "reordered": bool, "dropped": [...], "replaced": [...],
         "rescued_version_id": ...}}.
"""


@prompt(
    name="rescue_set_workflow",
    description="Repair a set riddled with hard-reject transitions (reorder -> cull -> bridge).",
    tags={"namespace:workflow", "review", "set_building"},
    meta=PROMPT_META,
)
def rescue_set_workflow(set_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id))],
        description=f"Heavy-repair rescue recipe for set {set_id}.",
    )
