"""subgenre_journey_workflow — plan a journey along the techno energy axis."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, arc: str) -> str:
    return f"""Plan a subgenre journey ('{arc}') from playlist {playlist_id}.

The 15 techno subgenres form an energy axis (read reference://subgenres):
  ambient_dub -> dub_techno -> minimal -> detroit -> melodic_deep ->
  progressive -> hypnotic -> driving -> tribal -> breakbeat ->
  peak_time -> acid -> raw -> industrial -> hard_techno
Move +/-1-2 steps between adjacent tracks for cohesion; a bigger jump is a
deliberate contrast moment. Note: 'driving' and 'hypnotic' are catch-all
labels (penalized by the classifier) — treat them as connective tissue, not
anchors.

Requested arc '{arc}':
- "build"   -> climb the axis low to high (warm-up into peak).
- "release" -> descend the axis high to low (closing / cool-down).
- "wave"    -> oscillate up and down in 2-3 energy waves.
- "plateau" -> hold one neighbourhood (e.g. hypnotic/driving roller).

1. Inventory subgenres present:
   entity_aggregate(entity="track_features", operation="distinct", field="mood",
                    filters={{"playlist_id": {playlist_id}}})
   then counts per mood:
   entity_aggregate(entity="track_features", operation="count",
                    filters={{"playlist_id": {playlist_id}, "mood": <m>}})

2. Draft the mood sequence honouring the arc and the axis-distance rule.
   Skip empty subgenres; bridge gaps with the nearest populated neighbour.

3. Pull candidate ids per mood bucket:
   entity_list(entity="track_features",
              filters={{"playlist_id": {playlist_id}, "mood__in": [...]}},
              fields="scoring")
   — prefer high mood_confidence tracks as the spine; low-confidence ones
     are flexible swing tracks.

4. Within each mood, keep BPM monotonic with the arc and Camelot distance
   low between neighbours (cross-check local://transition/{{a}}/{{b}}/score).

5. Order and persist:
   sequence_optimize(track_ids=[...], algorithm="ga")
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "subgenre_{arc}"}})

6. Sanity-check the narrative:
   local://sets/{{set_id}}/narrative — confirm the mood arc matches '{arc}'.

Return: {{"playlist_id": {playlist_id}, "arc": "{arc}",
         "mood_path": [...], "bpm_path": [...], "bridged_gaps": [...]}}.
"""


@prompt(
    name="subgenre_journey_workflow",
    description="Plan a techno subgenre journey (build/release/wave/plateau) on the energy axis.",
    tags={"namespace:workflow", "set_building", "mood"},
    meta=PROMPT_META,
)
def subgenre_journey_workflow(playlist_id: int, arc: str = "build") -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, arc))],
        description=f"Subgenre journey '{arc}' from playlist {playlist_id}.",
    )
