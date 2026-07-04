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
   Data guardrails:
   - Use schema://entities/track_features if any filter/payload name is uncertain.
   - Treat mood is a hint, not ground truth; confirm style with BPM, LUFS,
     energy_mean, spectral balance, hp_ratio and Beatport genre metadata.
   - If Beatport genre conflicts with classifier mood, mark it for review
     instead of silently trusting either label.
   - Features do not prove audio delivery: verify audio_file / physical MP3
     before promising L5 analysis, exact cue points or local export.

5. If the playlist is a broad crate, do staged narrowing before optimization:
   hard filters (BPM corridor, analysis level, audio availability when needed)
   -> style/feature filters -> diversity cap -> pair scoring -> final subset.
   Never send the whole library to sequence_optimize; it reorders a curated
   pool, it is not the crate-digging selector.

6. Compute pairwise scores across the candidate pool:
   transition_score_pool(track_ids=[...])

7. Optimize under the template arc:
   sequence_optimize(
       track_ids=[...],
       algorithm="ga",
       template="{template}",
   )
   - Use "ga" for arc-aware ordering of a curated pool.
   - Use "greedy" only when the pool is already tightly compatible and you
     need a fast nearest-neighbour chain.

8. Persist the ordered set as a new version:
   entity_create(entity="set_version", data={{
       "set_id": ...,
       "track_order": [...],
       "label": "v1"
   }})

9. Inspect the result:
   - Read local://sets/{{set_id}}/summary
   - Read local://sets/{{set_id}}/cheatsheet
   - Read local://sets/{{set_id}}/review  (watch for weak transitions / hard conflicts)

If any transition is flagged hard_reject, either pin the must-keep anchors
and re-run with a tighter curated pool, or inject a bridge track and rebuild.
For raw/hypnotic or low key_confidence material, use a groove-first reading:
BPM, low-end, energy and percussion continuity can outrank Camelot.

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
