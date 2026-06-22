"""fix_transition_workflow — diagnose and repair a single weak/rejected transition."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(a: int, b: int) -> str:
    return f"""Repair the {a} -> {b} transition.

1. Diagnose:
   local://transition/{a}/{b}/score   — overall, the 6 components
   (bpm, harmonic, energy, spectral, groove, timbral), hard_reject,
   reject_reason.
   local://transition/{a}/{b}/explain — narrative of which axis fails.
   ui_transition_score(from_track_id={a}, to_track_id={b}) — radar of the
   6 components (Prefab clients).

2. Identify the failure mode:
   - hard_reject by BPM (|Delta| > 10): tempo cliff.
   - hard_reject by Camelot (distance >= 5): keys clash.
   - hard_reject by energy (gap > 6 LUFS): loudness jump.
   - soft-weak (overall < 0.5, no reject): mixable but rough.

3. Choose a remedy in order of preference:

   a. TECHNIQUE (soft-weak, no hard_reject) — pick a transition style that
      hides the weak axis:
      - weak harmonic -> echo_out or filter-style move (mask the key clash).
      - weak groove/bpm -> long 32-bar blend with sync; EQ-trade the lows.
      - weak energy -> ride a breakdown; bass-swap into the drop.
      - weak timbral (vocal clash) -> vocal_cut / vocal_sustain.
      Confirm the engine's own pick is sane (the persisted transition row
      carries fx_type + a 32-bar recipe).

   b. BRIDGE (hard_reject) — find a 2-hop chain a -> x -> b:
      local://tracks/{a}/suggest_next?limit=15 — candidates that mix from a.
      For each candidate x, check local://transition/{a}/{{x}}/score AND
      local://transition/{{x}}/{b}/score — both must clear hard_reject.
      Insert the best x between them.

   c. REPLACE — if no bridge exists, swap b itself (run replace_track_workflow
      for b's position) or reorder so a/b are no longer adjacent.

4. Verify the fix:
   re-read local://transition/{a}/{{x}}/score and local://transition/{{x}}/{b}/score
   (or the new pair) — both overall >= 0.5 and hard_reject=False.

Return: {{"from": {a}, "to": {b}, "failure": ..., "remedy": "technique|bridge|replace",
         "bridge_track": ..., "style": ..., "resolved": true|false}}.
"""


@prompt(
    name="fix_transition_workflow",
    description="Diagnose a weak/hard-reject transition and repair it (technique/bridge/replace).",
    tags={"namespace:workflow", "reasoning", "transition"},
    meta=PROMPT_META,
)
def fix_transition_workflow(from_track_id: int, to_track_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(from_track_id, to_track_id))],
        description=f"Fix transition {from_track_id} -> {to_track_id}.",
    )
