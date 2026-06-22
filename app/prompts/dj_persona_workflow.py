"""dj_persona_workflow — build a set in the style of a named DJ school/persona."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META

# persona -> (template, mood band, ethos). Templates are real entries in
# app/domain/template/registry.py; moods are real subgenres in
# app/shared/constants.py. Do not invent names.
_PERSONAS: dict[str, tuple[str, str, str]] = {
    "klock": (
        "roller_90",
        "dub_techno, hypnotic, driving",
        "BERGHAIN / Ben Klock ethos: hypnotic warehouse depth. Loopy, grainy, "
        "patient builds; treat track elements (kick, hats, bass, stab) as "
        "bricks that enter and leave quickly and smoothly — tease tracks in and "
        "out. Long 32-bar blends, HARMONIC_SUSTAIN where keys allow. Selection "
        "matters as much as technique; locked groove over flashy cuts.",
    ),
    "dettmann": (
        "peak_hour_60",
        "driving, raw, industrial",
        "Marcel Dettmann ethos: raw, steely, percussive Berlin techno. Reduced "
        "but heavy; metallic textures, dub space, then weight. Drum-led "
        "transitions (DRUM_SWAP / DRUM_CUT), restrained melody, relentless but "
        "controlled drive. Dark and physical, never cluttered.",
    ),
    "lens": (
        "peak_hour_60",
        "peak_time, acid, hard_techno",
        "Amelie Lens ethos: high-octane acid-leaning peak time. TB-303 "
        "resonance, hard kicks, festival drive. Tight BPM band high in the "
        "range, short bass-swap transitions, 2-3 signature hands-up cuts spaced "
        "by groove tracks. Energy stays up — do not let the floor cool.",
    ),
    "dewitte": (
        "peak_hour_60",
        "peak_time, acid, hard_techno",
        "Charlotte de Witte ethos: dark, driving, acid peak time. Stripped-back "
        "hypnotic menace into hard kicks and 303 lines. Relentless forward "
        "motion, minimal harmonic distraction, surgical energy management.",
    ),
    "mills": (
        "classic_60",
        "detroit, driving, peak_time",
        "Jeff Mills ethos: fast Detroit machine-soul, three-deck mentality. "
        "Dense phrasing, quick blends, string stabs and futurist funk over a "
        "relentless engine. Short overlaps, constant motion, treat the mixer "
        "like an instrument.",
    ),
    "hawtin": (
        "roller_90",
        "minimal, dub_techno, hypnotic",
        "Richie Hawtin / Plastikman ethos: minimal, micro-detailed, hypnotic. "
        "Reduction and repetition; tiny variations carry the journey. Quiet "
        "kicks, deep space, surgical EQ and filter movements over very long "
        "blends. Reward patience, not bangers.",
    ),
    "kraviz": (
        "roller_90",
        "hypnotic, acid, raw",
        "Nina Kraviz ethos: hypnotic, leftfield, acid-tinged. Raw and trippy, "
        "filter-driven tension, unexpected selection. Loopy hypnotic spine with "
        "acid stabs; embrace texture and grit over polish.",
    ),
}


def _body(playlist_id: int, persona: str, length: int) -> str:
    template, moods, ethos = _PERSONAS.get(persona, _PERSONAS["klock"])
    return f"""Build a ~{length}-track set from playlist {playlist_id} in the
style of the '{persona}' DJ persona, using template '{template}'.

{ethos}

Honesty: this maps a school's AESTHETIC onto our engine (template + subgenre
band + transition character). The engine has no real stem separation and no
FILTER_SWEEP/LOOP_ROLL presets — approximate filter/loop moves with the
available picker presets and longer blends. Do not promise live FX the engine
cannot render.

1. Prime once: invoke dj_expert_session for Camelot / subgenres / templates.

2. Read the persona's energy contract:
   reference://templates  — the '{template}' slots (position, mood, target_lufs,
   bpm range). This is the arc the set must honour.
   reference://subgenres  — confirm the character band: {moods}.

3. Resolve + ready the pool (track has no playlist_id column):
   local://playlists/{playlist_id}?include_tracks=true -> pool_ids = [...]
   entity_list(entity="track_features", filters={{"track_id__in": pool_ids}},
              fields="scoring")
   — ensure level >= 3; analyze_library_workflow first for stragglers.

4. Select to character: keep tracks whose mood sits in the persona band
   ({moods}); drop clear outliers (e.g. melodic_deep in a Lens set, hard_techno
   in a Hawtin set):
   entity_list(entity="track_features",
              filters={{"track_id__in": pool_ids,
                       "mood__in": [<persona moods>]}}, fields="scoring")

5. Order under the template arc with the persona's transition feel:
   sequence_optimize(track_ids=[...], algorithm="ga", template="{template}")
   — long blends / HARMONIC_SUSTAIN for Klock/Hawtin; tight bass-swaps and
     hands-up cuts for Lens/de Witte; quick dense blends for Mills.

6. Persist + critique against the persona:
   entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "persona_{persona}"}})
   local://sets/{{set_id}}/narrative — does the arc read like '{persona}'?
   local://sets/{{set_id}}/review    — weak transitions / hard conflicts.
   ui_set_view(set_id=<id>)          — visual energy arc.

7. If the set drifts off-character, pin the most on-brand anchors and re-run
   sequence_optimize, or swap offenders via replace_track_workflow.

Return: {{"playlist_id": {playlist_id}, "persona": "{persona}",
         "template": "{template}", "set_id": ..., "version_id": ...,
         "quality_score": ...}}.
"""


@prompt(
    name="dj_persona_workflow",
    description=(
        "Build a set in the style of a named DJ persona "
        "(klock/dettmann/lens/dewitte/mills/hawtin/kraviz)."
    ),
    tags={"namespace:workflow", "set_building", "persona"},
    meta=PROMPT_META,
)
def dj_persona_workflow(
    playlist_id: int,
    persona: str = "klock",
    length: int = 12,
) -> PromptResult:
    template = _PERSONAS.get(persona, _PERSONAS["klock"])[0]
    return PromptResult(
        messages=[Message(_body(playlist_id, persona, length))],
        description=f"Persona set '{persona}' ({template}) from playlist {playlist_id}.",
    )
