"""b2b_planning_workflow — plan a back-to-back set across two DJs/crates."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_a: int, playlist_b: int, template: str) -> str:
    return f"""Plan a back-to-back (B2B) set from two crates:
DJ-A = playlist {playlist_a}, DJ-B = playlist {playlist_b}, template '{template}'.

B2B etiquette (decide BEFORE building): who opens / who closes, how tracks
alternate, who owns which FX. Read the energy TOGETHER — going big too early
is doubly costly in a B2B because the partner must either match or visibly
bring it down. The better warm-up DJ opens; the stronger closer lands it.

1. Tag both crates so fast swapping is possible. track_features has no
   playlist_id column, so first resolve each crate's track ids, then filter
   features by track_id__in:
   local://playlists/{playlist_a}?include_tracks=true -> ids_a = [...]
   local://playlists/{playlist_b}?include_tracks=true -> ids_b = [...]
   entity_list(entity="track_features", filters={{"track_id__in": ids_a}},
              fields="scoring")
   entity_list(entity="track_features", filters={{"track_id__in": ids_b}},
              fields="scoring")
   — both crates must be at level >= 3; analyze gaps first.

2. Split the template arc into alternating ownership:
   reference://templates — read '{template}' slots. Assign odd slots to DJ-A,
   even slots to DJ-B (or agree opener/closer and alternate from there). Each
   DJ supplies the track for their slot from their own crate.

3. The hand-off rule: every cross-DJ transition (A-track -> B-track) is the
   risky seam. For each planned hand-off:
   local://transition/<a_track>/<b_track>/score — must clear hard_reject and
   ideally overall >= 0.6 (cross-crate keys/BPM drift more than within a crate).
   Keep BPM continuity across the seam (+/-2-3 BPM); align Camelot distance <= 2.

4. Build the interleaved order and let the optimizer smooth seams while
   respecting ownership (pin each DJ's chosen anchors):
   sequence_optimize(track_ids=[<interleaved a/b ids>], algorithm="ga",
                    template="{template}", pinned=[<anchor ids>])

5. Persist and review the seams specifically:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "b2b"}})
   local://sets/{{set_id}}/review — pay attention to the A<->B boundary pairs.
   ui_set_view(set_id=<id>) — confirm a single coherent arc, not two stitched
   half-sets.

6. Produce the shared cheatsheet both DJs read live:
   local://sets/{{set_id}}/cheatsheet — BPM/key/energy per slot + whose track.

Return: {{"set_id": ..., "ownership": {{"A": [...positions], "B": [...]}},
         "handoff_seams": [...], "weak_seams": [...], "quality_score": ...}}.
"""


@prompt(
    name="b2b_planning_workflow",
    description="Plan a back-to-back set across two crates: split the arc, smooth the hand-offs.",
    tags={"namespace:workflow", "set_building", "b2b"},
    meta=PROMPT_META,
)
def b2b_planning_workflow(
    playlist_a: int,
    playlist_b: int,
    template: str = "classic_60",
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_a, playlist_b, template))],
        description=f"B2B plan: playlists {playlist_a} + {playlist_b} ({template}).",
    )
