"""lineup_handoff_workflow — build a slot that hands off cleanly to the next DJ."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META

# role -> (template, end-direction, ethos). Templates are real entries in
# app/domain/template/registry.py.
_ROLES: dict[str, tuple[str, str, str]] = {
    "warmup": (
        "warm_up_30",
        "up",
        "WARM-UP handoff: support the room and hand it over WARM but not peaked. "
        "Never exceed the headliner's tempo; land the tail AT the handoff BPM/"
        "energy so the next DJ steps in smoothly. Restraint over bangers — build, "
        "do not blow the roof early.",
    ),
    "headliner": (
        "peak_hour_60",
        "flat",
        "HEADLINER slot: take the warm floor to the peak and hold it. Enter near "
        "the incoming BPM/energy you were handed, drive through the peak, and "
        "leave the tail high (or begin the descent if you also close).",
    ),
    "closer": (
        "closing_60",
        "down",
        "CLOSER handoff: bring the floor DOWN gracefully toward the end of the "
        "night. Enter near the peak you were handed, then descend the energy axis "
        "to a soft landing — the tail BPM/energy should feel like an ending.",
    ),
}


def _body(playlist_id: int, role: str, handoff_bpm: int) -> str:
    template, direction, ethos = _ROLES.get(role, _ROLES["warmup"])
    return f"""Build a '{role}' lineup slot from playlist {playlist_id} that
hands off cleanly to the next DJ, ending around {handoff_bpm} BPM
(template '{template}', tail energy direction '{direction}').

{ethos}

Where b2b_planning_workflow splits one booth between two DJs ALTERNATING, this
plans ONE sequential slot whose TAIL is engineered for the handover — the most
under-appreciated DJ skill (Red Bull / Mixmag warm-up etiquette).

1. Prime once: invoke dj_expert_session for BPM / Camelot / template rules.

2. Read the slot's energy contract:
   reference://templates — the '{template}' slots (position, mood, target_lufs,
   bpm range). The handoff target sits at the TAIL of this arc.

3. Resolve + ready the pool (track has no playlist_id column):
   local://playlists/{playlist_id}?include_tracks=true -> pool_ids = [...]
   entity_list(entity="track_features", filters={{"track_id__in": pool_ids}},
              fields="scoring")
   — ensure level >= 3; analyze_library_workflow first for stragglers.

4. Pick the HANDOFF TRACK first — the last track of the slot must sit at the
   target so the next DJ can mix straight out of it:
   entity_list(entity="track_features",
              filters={{"track_id__in": pool_ids, "bpm__gte": {handoff_bpm - 2},
                       "bpm__lte": {handoff_bpm + 2}}}, fields="scoring")
   — for 'warmup'/'headliner' the tail holds energy; for 'closer' the tail is
     the lowest-energy landing. Note its key_code for a clean outgoing mix.

5. Order the slot so the arc climbs/holds/descends INTO that tail, pinning the
   handoff track last (and the opener first):
   sequence_optimize(track_ids=[...], algorithm="ga", template="{template}",
                    pinned=[<opener_id>, <handoff_track_id>])

6. Persist + verify the landing:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "handoff_{role}"}})
   local://sets/{{set_id}}/narrative — does the tail land at ~{handoff_bpm} BPM
   and the right energy for a '{role}' handoff?
   ui_set_view(set_id=<id>) — the arc should resolve cleanly at the tail.

7. If the tail overshoots the headliner's tempo (warm-up) or ends too hot
   (closer), swap the handoff track via replace_track_workflow and re-pin.

Return: {{"playlist_id": {playlist_id}, "role": "{role}",
         "handoff_bpm": {handoff_bpm}, "template": "{template}",
         "set_id": ..., "version_id": ..., "handoff_track_id": ...}}.
"""


@prompt(
    name="lineup_handoff_workflow",
    description="Build a lineup slot (warmup/headliner/closer) whose tail hands off at a set BPM.",
    tags={"namespace:workflow", "set_building", "lineup"},
    meta=PROMPT_META,
)
def lineup_handoff_workflow(
    playlist_id: int,
    role: str = "warmup",
    handoff_bpm: int = 128,
) -> PromptResult:
    template = _ROLES.get(role, _ROLES["warmup"])[0]
    return PromptResult(
        messages=[Message(_body(playlist_id, role, handoff_bpm))],
        description=f"Lineup '{role}' slot ({template}) handing off at {handoff_bpm} BPM.",
    )
