"""scenario_set_workflow — scenario-driven set building (warmup/peak/closing/...)."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META

# scenario -> (template, role guidance). Templates are real entries in
# app/domain/template/registry.py; do not invent names.
_SCENARIOS: dict[str, tuple[str, str]] = {
    "warmup": (
        "warm_up_30",
        "OPENER ethos: restraint over bangers. Never exceed the headliner's "
        "BPM; leave the next DJ a sane tempo. Stay low-mid energy, longer "
        "blends, deeper/dubbier selections (ambient_dub -> melodic_deep). "
        "Build the room, do not peak it.",
    ),
    "peak": (
        "peak_hour_60",
        "PEAK ethos: relentless drive. Keep energy high throughout "
        "(driving/peak_time/acid/industrial). Tight BPM band, hard kicks, "
        "short bass-swap transitions. Punctuate with 2-3 signature 'hands-up' "
        "cuts spaced by groove tracks — do not stack every banger back to back.",
    ),
    "closing": (
        "closing_60",
        "CLOSER ethos: graceful wind-down. Descend the energy axis "
        "(driving -> melodic_deep -> dub_techno -> ambient_dub). Longer, more "
        "emotional blends; room for one nostalgic / experimental moment. Land "
        "the floor softly, do not slam the doors.",
    ),
    "roller": (
        "roller_90",
        "ROLLER ethos: sustained hypnotic groove. Minimal energy swings, "
        "loopy/driving/hypnotic selections, locked BPM. The journey is the "
        "repetition — reward patience with subtle filter and EQ movements.",
    ),
    "wave": (
        "wave_120",
        "WAVE ethos: multiple build-release cycles over 2 hours. Each wave "
        "climbs to a mini-peak then breathes back down before the next climb. "
        "Use breakdowns as the valleys between waves.",
    ),
    "progressive": (
        "progressive_120",
        "PROGRESSIVE ethos: one slow 2-hour ramp. Imperceptible +1 BPM moves, "
        "patient subgenre climb (ambient_dub -> peak_time). The set should feel "
        "like a single continuous build with no abrupt jumps.",
    ),
}


def _body(playlist_id: int, scenario: str) -> str:
    template, ethos = _SCENARIOS.get(scenario, _SCENARIOS["peak"])
    return f"""Build a '{scenario}' set from playlist {playlist_id}
using template '{template}'.

{ethos}

1. Prime once if not already: invoke the dj_expert_session prompt to load
   Camelot / subgenres / templates / audit knowledge.

2. Inspect the slot's target arc:
   reference://templates — read the '{template}' slots (position, mood,
   target_lufs, bpm range). This is the energy contract the set must honour.

3. Pull and ready the pool (ensure level >= 3):
   entity_list(entity="track_features", filters={{"playlist_id": {playlist_id}}},
              fields="scoring")
   — for any track below level 3, run the analyze_library_workflow prompt
     first (sequence_optimize auto-upgrades, but pre-analysis is faster).

4. Filter to the scenario's character: keep tracks whose mood + BPM + LUFS
   fit the '{template}' slots; drop clear mismatches (e.g. ambient_dub in a
   peak set, hard_techno in a warm-up).

5. Order under the template arc:
   sequence_optimize(track_ids=[...], algorithm="ga", template="{template}")
   — the GA reads the per-template phase table so intent (ramp_up / maintain /
     cool_down) tracks the '{scenario}' shape.

6. Persist + inspect:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "{scenario}"}})
   local://sets/{{set_id}}/review     — weak transitions / hard conflicts.
   local://sets/{{set_id}}/narrative  — does the arc read as '{scenario}'?
   ui_set_view(set_id=<id>)           — visual energy arc (Prefab clients).

7. If the arc fights the scenario (e.g. peaks too early for a warm-up), pin
   the anchors and re-run sequence_optimize, or swap offenders via the
   replace_track_workflow prompt.

Return: {{"playlist_id": {playlist_id}, "scenario": "{scenario}",
         "template": "{template}", "set_id": ..., "version_id": ...,
         "quality_score": ...}}.
"""


@prompt(
    name="scenario_set_workflow",
    description="Build a scenario-driven set (warmup/peak/closing/roller/wave/progressive).",
    tags={"namespace:workflow", "set_building", "scenario"},
    meta=PROMPT_META,
)
def scenario_set_workflow(playlist_id: int, scenario: str = "peak") -> PromptResult:
    template = _SCENARIOS.get(scenario, _SCENARIOS["peak"])[0]
    return PromptResult(
        messages=[Message(_body(playlist_id, scenario))],
        description=f"Scenario set '{scenario}' ({template}) from playlist {playlist_id}.",
    )
