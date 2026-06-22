"""tempo_journey_workflow — order a set as a deliberate BPM ramp (tempo axis)."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, start_bpm: int, end_bpm: int, length: int) -> str:
    direction = "climb" if end_bpm >= start_bpm else "descend"
    span = abs(end_bpm - start_bpm)
    per_step = round(span / max(length - 1, 1), 2)
    return f"""Build a ~{length}-track set from playlist {playlist_id} that
{direction}s the TEMPO axis from {start_bpm} to {end_bpm} BPM.

This is the third journey axis alongside harmonic_journey_workflow (Camelot
key) and subgenre_journey_workflow (mood/energy). Here BPM is the spine: a
gradual ramp the floor FEELS but does not consciously HEAR.

Craft rule (from professional practice): move ~+1-2 BPM per transition, never
more than the hard-reject ceiling |dBPM| > 10. Across {length} tracks that is
~{per_step} BPM/step. Big jumps must hide in a breakdown, a half/double-time
track, or a deliberate reset — never as a raw cut.

1. Prime once: invoke dj_expert_session to load BPM / Camelot / template rules.

2. Resolve the pool ids (track has no playlist_id column):
   local://playlists/{playlist_id}?include_tracks=true -> pool_ids = [...]

3. Read tempo + scoring features for the pool, ensure level >= 3:
   entity_list(entity="track_features", filters={{"track_id__in": pool_ids}},
              fields="scoring")
   — for tracks below level 3, run analyze_library_workflow first
     (sequence_optimize auto-upgrades, but pre-analysis is faster).
   entity_aggregate(entity="track_features", operation="histogram",
                    field="bpm")  — see how the pool is distributed.

4. Keep only tracks inside the ramp band; trim outliers that would force a
   tempo cliff:
   entity_list(entity="track_features",
              filters={{"track_id__in": pool_ids, "bpm__gte": {min(start_bpm, end_bpm)},
                       "bpm__lte": {max(start_bpm, end_bpm)}}}, fields="scoring")
   — flag variable_tempo tracks (filters={{"variable_tempo": true}}); they
     wobble the ramp, place them on plateaus not on steep steps.

5. Order under a tempo-aware ramp. Pin the slowest track first and the fastest
   last so the GA threads a monotonic {direction}:
   sequence_optimize(track_ids=[...], algorithm="ga", template="progressive_120")
   — progressive_120's phase table rewards one long imperceptible ramp; for a
     short set use "classic_60". Pin anchors:
     sequence_optimize(..., pinned=[<slowest_id>, <fastest_id>])

6. Persist + verify the ramp reads as intended:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "tempo_{start_bpm}_{end_bpm}"}})
   local://sets/{{set_id}}/review     — no |dBPM| hard_rejects on the steps.
   local://sets/{{set_id}}/narrative  — does the energy track the tempo {direction}?
   ui_set_view(set_id=<id>)           — visual arc (Prefab clients).

7. If a single step exceeds the BPM ceiling, insert a bridge track at that BPM
   or run replace_track_workflow for the offending slot.

Return: {{"playlist_id": {playlist_id}, "start_bpm": {start_bpm},
         "end_bpm": {end_bpm}, "set_id": ..., "version_id": ...,
         "quality_score": ...}}.
"""


@prompt(
    name="tempo_journey_workflow",
    description="Order a set as a gradual BPM ramp along the tempo axis (start_bpm -> end_bpm).",
    tags={"namespace:workflow", "set_building", "journey"},
    meta=PROMPT_META,
)
def tempo_journey_workflow(
    playlist_id: int,
    start_bpm: int = 122,
    end_bpm: int = 132,
    length: int = 12,
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, start_bpm, end_bpm, length))],
        description=(
            f"Tempo-ramp set {start_bpm}->{end_bpm} BPM "
            f"(~{length} tracks) from playlist {playlist_id}."
        ),
    )
