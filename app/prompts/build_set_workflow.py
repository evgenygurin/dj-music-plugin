"""build_set_workflow — step-by-step recipe for building a set."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _build_body(playlist_id: int, template: str) -> str:
    return f"""To build a set from playlist {playlist_id} with template '{template}':

1. Load playlist items and their track IDs:
   entity_get(entity="playlist", id={playlist_id}, include_relations=["items"])
   (each item carries track_id + sort_index)

2. For every track lacking analysis level >= 3, schedule analysis:
   entity_create(entity="track_features", data={{"track_ids": [...], "level": 3}})

3. Audit each track against techno criteria:
   - Read local://tracks/{{id}}/audit for each and drop any with hard violations.

4. Build the candidate pool (features projection):
   entity_list(entity="track_features", filters={{"track_id__in": [...]}}, fields="scoring")

5. Compute pairwise scores across the candidate pool:
   transition_score_pool(track_ids=[...])

6. Optimize under the template arc:
   sequence_optimize(
       track_ids=[...],
       algorithm="constructive",
       template="{template}",
   )
   - Use "constructive" when the playlist is a broad candidate crate and
     you want the engine to choose the exact slot occupants under the
     template.
   - Use "ga" / "greedy" only when you already trust the pool and only
     want re-ordering.

7. Persist the ordered set as a new version:
   entity_create(entity="set_version", data={{
       "set_id": ...,
       "track_order": [...],
       "label": "v1"
   }})

8. Inspect the result:
   - Read local://sets/{{set_id}}/summary
   - Read local://sets/{{set_id}}/cheatsheet
   - Read local://sets/{{set_id}}/review  (watch for weak transitions / hard conflicts)

If any transition is flagged hard_reject, either pin the must-keep anchors
and re-run constructive selection, or inject a bridge track and rebuild.

Return: {{"set_id": ..., "version_id": ..., "quality_score": ...}}
"""


@prompt(
    name="build_set_workflow",
    description="Recipe for building a DJ set from a playlist end-to-end.",
    tags={"namespace:workflow", "set_building"},
    meta=PROMPT_META,
)
def build_set_workflow(playlist_id: int, template: str = "classic_60") -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(playlist_id, template))],
        description=f"Recipe: build set from playlist {playlist_id} with template '{template}'.",
    )
