"""set_review_workflow — critique an existing set and propose fixes."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int) -> str:
    return f"""Critique set {set_id} like a seasoned techno selector and
propose concrete fixes.

1. Establish the current state:
   local://sets/{set_id}/summary  — version_id, track count, quality_score.
   local://sets/{set_id}/tracks   — ordered (track_id, title, position).

2. Energy arc & narrative:
   local://sets/{set_id}/narrative — does it read warm-up -> build -> peak ->
   release (or whatever the template promised)? Flag premature peaks, energy
   sag in the middle, or a flat line that never lifts.
   ui_set_view(set_id={set_id}) — eyeball the energy arc + per-slot table.
   Treat mood is a hint, not ground truth: when the narrative claims a style,
   cross-check BPM, LUFS, energy_mean, spectral balance, hp_ratio and Beatport
   genre metadata. If Beatport genre conflicts with classifier mood, report the
   conflict instead of declaring one label correct.

3. Transition quality:
   local://sets/{set_id}/review — list weak transitions (overall < 0.5) and
   hard_conflicts (hard_reject=True). For each weak/hard pair read
   local://transition/{{a}}/{{b}}/explain to see which component fails
   (bpm / harmonic / energy / spectral / groove / timbral).

4. Diagnose patterns, not just points:
   - Repeated harmonic failures -> the key journey is broken (see
     harmonic_journey_workflow).
   - Repeated bpm failures -> a tempo cliff; insert a reset or reorder.
   - Clustered hard_rejects -> a foreign-character track wandered in.
   - Raw/hypnotic or low key_confidence material may need a groove-first read:
     judge BPM, low-end, energy and percussion continuity before over-weighting
     Camelot.
   - Missing sections/beatgrid/downbeats means mix points are approximate.
     Missing audio_file / physical MP3 means delivery readiness is not proven.
     Use schema://entities/track_features or schema://entities/audio_file when
     the data contract is unclear.

5. Prescribe fixes, cheapest first:
   a. Reorder: sequence_optimize(track_ids=<current ids>, algorithm="ga",
      template=<set template>) and compare quality_score.
   b. Replace a single offender: run the replace_track_workflow prompt for
      that position.
   c. Bridge a hard pair: run the fix_transition_workflow prompt.
   d. If the set came from a broad crate, rebuild via staged narrowing:
      hard filters -> style/feature filters -> diversity cap -> pair scoring.

6. If you applied a fix, persist a new version and diff:
   entity_create(entity="set_version", data={{"set_id": {set_id},
                "track_order": [...], "label": "review_fix"}})
   local://sets/{set_id}/versions/compare/<old>/<new> — confirm the score
   improved and no new hard conflicts appeared.

Return: {{"set_id": {set_id}, "quality_score": ..., "weak_transitions": [...],
         "hard_conflicts": [...], "arc_issues": [...], "fixes_applied": [...],
         "new_version_id": ...}}.
"""


@prompt(
    name="set_review_workflow",
    description="Critique an existing set (arc, transitions, conflicts) and propose fixes.",
    tags={"namespace:workflow", "review", "set_building"},
    meta=PROMPT_META,
)
def set_review_workflow(set_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id))],
        description=f"Review + fix recipe for set {set_id}.",
    )
