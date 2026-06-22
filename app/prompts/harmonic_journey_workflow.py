"""harmonic_journey_workflow — plan a Camelot key-journey across a set."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, length: int, start_camelot: str | None) -> str:
    start_clause = (
        f"Anchor the journey at {start_camelot} (resolve key_code via reference://camelot)."
        if start_camelot
        else "Pick the start key from the densest available Camelot slot "
        "(most candidates = most freedom)."
    )
    return f"""Plan a ~{length}-track harmonic journey from playlist {playlist_id}.

Harmonic-mixing rules (Camelot wheel — read reference://camelot first):
- Same key (distance 0) = seamless.
- +/-1 on the wheel (distance 1) = adjacent, very smooth.
- A<->B same number = relative minor/major mood-switch (minor darker /
  driving, major brighter / lifting).
- +2 clockwise = "energy boost": more distance, do it FAST, as a nagging
  lift. Our scorer caps safe Camelot distance at 4 (>=5 hard-rejects).

1. Load candidate keys:
   entity_list(entity="track_features", filters={{"playlist_id": {playlist_id}}},
              fields="scoring")
   — group track_ids by key_code; map key_code -> Camelot via reference://camelot.

2. Survey supply:
   entity_aggregate(entity="track_features", operation="histogram",
                    field="key_code", filters={{"playlist_id": {playlist_id}}})
   — thin keys are dead-ends; route around them.

3. {start_clause}

4. Walk the wheel: hold 2-3 tracks per key, then move 1 step (or A<->B for a
   mood flip, or +2 for a deliberate lift). Avoid distance >=3 jumps unless
   bridged. Keep BPM drift within +/-4 across each move.

5. Validate each chosen hop:
   local://transition/{{a}}/{{b}}/score   — confirm overall and that
   hard_reject is false; read local://transition/{{a}}/{{b}}/explain to see
   the harmonic component.

6. Lock the ordered ids and hand off:
   sequence_optimize(track_ids=[...], algorithm="greedy")
   — greedy respects the harmonic chain you built without reshuffling it as
     aggressively as the GA.

7. Persist if happy:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "harmonic_journey"}})

Return: {{"playlist_id": {playlist_id}, "camelot_path": ["8A","8A","9A",...],
         "bpm_path": [...], "weak_hops": [...]}}.
"""


@prompt(
    name="harmonic_journey_workflow",
    description="Plan a Camelot-wheel key journey (harmonic mixing) across a track run.",
    tags={"namespace:workflow", "harmonic", "set_building"},
    meta=PROMPT_META,
)
def harmonic_journey_workflow(
    playlist_id: int,
    length: int = 12,
    start_camelot: str | None = None,
) -> PromptResult:
    anchor = f" from {start_camelot}" if start_camelot else ""
    return PromptResult(
        messages=[Message(_body(playlist_id, length, start_camelot))],
        description=f"Harmonic journey{anchor}: {length} tracks from playlist {playlist_id}.",
    )
