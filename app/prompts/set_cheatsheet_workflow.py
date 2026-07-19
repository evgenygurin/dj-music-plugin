"""set_cheatsheet_workflow — produce a performance-ready cue sheet for a set."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(set_id: int, version: int | None) -> str:
    ver = f"?version={version}" if version is not None else ""
    ver_note = f" (version {version})" if version is not None else " (latest version)"
    return f"""Produce a performance-ready cheat sheet for set {set_id}{ver_note}
that a DJ can read mid-set without doing any analysis live.

This is a READ-ONLY assembly job: no reordering, no new version. Turn the
persisted set + transitions into a single per-track crib sheet.

1. Pull the engine's own cheat sheet first:
   local://sets/{set_id}/cheatsheet{ver}
   — this already renders the DJ-facing text (per-slot BPM/key/mix notes).
   local://sets/{set_id}/tracks — ordered (position, track_id, title).
   local://sets/{set_id}/summary — template, quality_score, version_id.

2. Pull the persisted transitions for the per-pair technique:
   dj_entity_list(entity="transition",
              filters={{"from_track_id__in": [<set track ids>]}},
              fields="full")
   — each row carries fx_type (the chosen Neural Mix preset: FADE / ECHO_OUT /
     DRUM_SWAP / DRUM_CUT / VOCAL_SUSTAIN / VOCAL_CUT / HARMONIC_SUSTAIN),
     overall_quality, and transition_bars (blend length). The "summary" preset
     omits transition_bars/overlap_ms, so use "full" here.
   For any pair you want to double-check, read
   local://transition/{{a}}/{{b}}/explain for the component breakdown.

3. Pull the scoring features for the marquee numbers per track:
   dj_entity_list(entity="track_features", filters={{"track_id__in": [...]}},
              fields="scoring")
   — bpm, key_code (-> Camelot via reference://camelot), integrated_lufs
     (energy), mood (subgenre).

4. Assemble ONE row per track in play order. Recommended columns:
   pos | title | BPM | Camelot | mood | LUFS | -> next: fx_type @ N bars (quality)
   Add a short cue for the OUTGOING mix of each track:
   - HARMONIC_SUSTAIN / FADE -> "long 32-bar blend, keys lock"
   - DRUM_SWAP / DRUM_CUT     -> "EQ the bass out, swap on the drums"
   - ECHO_OUT                 -> "echo tail on the last bar, pull the fader"
   - VOCAL_SUSTAIN / VOCAL_CUT-> "ride the vocal over the incoming groove"

5. Flag the danger spots up top so the DJ sees them first:
   local://sets/{set_id}/review — list any hard_reject pairs and weak
   (overall < 0.5) transitions; these are the moments to ride manually or
   fix beforehand via fix_transition_workflow.

6. Honesty note for the sheet: mix-in/out points come from track_sections
   (auto), NOT from manual hot cues (dj_cue_points is empty) and downbeat
   alignment uses fallback 0 (dj_beatgrids ~0.1% coverage). Phrase-align by
   ear on the night.

Return a compact markdown table (play order) plus a "watch-outs" list of the
hard/weak transitions, ready to print or read on a phone.
"""


@prompt(
    name="set_cheatsheet_workflow",
    description="Assemble a performance-ready DJ cue sheet (BPM/key/energy/technique) for a set.",
    tags={"namespace:workflow", "delivery", "performance"},
    meta=PROMPT_META,
)
def set_cheatsheet_workflow(set_id: int, version_id: int | None = None) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, version_id))],
        description=f"Performance cheat sheet for set {set_id}.",
    )
