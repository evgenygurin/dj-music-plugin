"""quick_mix_check — pair compatibility shortcut."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(a: int, b: int) -> str:
    return f"""Quickly assess the {a} -> {b} transition:

1. Ensure both tracks have features at analysis_level >= 3:
   - local://tracks/{a}/features   (expect bpm, key, lufs, energy)
   - local://tracks/{b}/features

2. Read the pairwise score:
   local://transition/{a}/{b}/score
   — components: bpm, harmonic, energy, spectral, groove, timbral.
   — flags: hard_reject, reject_reason.

3. Read the narrative explanation:
   local://transition/{a}/{b}/explain

4. Interpret:
   - overall >= 0.75 -> smooth, bass-swap 8 bars.
   - 0.50 <= overall < 0.75 -> long blend 32 bars or EQ-trade.
   - overall < 0.50 -> echo-out or filter-sweep; consider a bridge track.
   - hard_reject=True -> do NOT mix; find a bridge (2-hop chain via suggest_next).

Return: {{"from": {a}, "to": {b}, "overall": ..., "hard_reject": ...,
         "style": ...,  "suggestion": ...}}.
"""


@prompt(
    name="quick_mix_check",
    description="Inspect a single pairwise mix compatibility (a -> b).",
    tags={"namespace:workflow", "reasoning"},
    meta=PROMPT_META,
)
def quick_mix_check(track_a_id: int, track_b_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(track_a_id, track_b_id))],
        description=f"Quick mix check: {track_a_id} -> {track_b_id}.",
    )
