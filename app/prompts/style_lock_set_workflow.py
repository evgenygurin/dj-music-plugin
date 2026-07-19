"""style_lock_set_workflow — build a set locked to a single subgenre/style band."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META

# style -> (neighbour moods to allow, template). All moods are real subgenres
# (app/shared/constants.py); templates are real (app/domain/template/registry.py).
_STYLES: dict[str, tuple[str, str]] = {
    "ambient_dub": ("ambient_dub, dub_techno", "warm_up_30"),
    "dub_techno": ("dub_techno, ambient_dub, minimal", "roller_90"),
    "minimal": ("minimal, dub_techno, detroit", "roller_90"),
    "detroit": ("detroit, minimal, melodic_deep", "classic_60"),
    "melodic_deep": ("melodic_deep, detroit, progressive", "classic_60"),
    "progressive": ("progressive, melodic_deep, hypnotic", "progressive_120"),
    "hypnotic": ("hypnotic, driving, dub_techno", "roller_90"),
    "driving": ("driving, hypnotic, peak_time", "roller_90"),
    "tribal": ("tribal, driving, peak_time", "peak_hour_60"),
    "peak_time": ("peak_time, driving, acid", "peak_hour_60"),
    "acid": ("acid, peak_time, raw", "peak_hour_60"),
    "raw": ("raw, acid, industrial", "peak_hour_60"),
    "industrial": ("industrial, raw, hard_techno", "peak_hour_60"),
    "hard_techno": ("hard_techno, industrial, peak_time", "peak_hour_60"),
}


def _body(playlist_id: int, style: str, length: int) -> str:
    band, template = _STYLES.get(style, _STYLES["hypnotic"])
    return f"""Build a ~{length}-track set from playlist {playlist_id} LOCKED to
the '{style}' style — a mono-genre set, not a journey across subgenres.

Use subgenre_journey_workflow when you want to MOVE across the energy axis.
Here we stay inside one character band ({band}) and create variety through
TEXTURE and ARRANGEMENT, not genre changes: follow a bright/airy track with a
darker bass-heavy one at the same energy, vary the percussion density, breathe
with a stripped-back tool, then lift again. The intensity holds; the character
shifts. Template '{template}' supplies the energy contract.

1. Prime once: invoke dj_expert_session for subgenres / templates / audit rules.

2. Confirm the band:
   reference://subgenres — '{style}' sits on the energy axis; the allowed
   neighbours are {band} (one step on either side keeps the set coherent
   without sounding monotone).

3. Resolve the pool (track has no playlist_id column) and ready features:
   local://playlists/{playlist_id}?include_tracks=true -> pool_ids = [...]
   dj_entity_list(entity="track_features", filters={{"track_id__in": pool_ids}},
              fields="scoring")
   — ensure level >= 3; analyze_library_workflow first for stragglers.
   If any field/filter is uncertain, read schema://entities/track_features.
   Treat mood is a hint: confirm the style lock with BPM, LUFS, energy_mean,
   spectral balance, hp_ratio and Beatport genre metadata. If Beatport genre
   disagrees with classifier mood, keep the candidate only after review.

4. Lock the selection to the style band:
   dj_entity_list(entity="track_features",
              filters={{"track_id__in": pool_ids, "mood__in": [<band moods>]}},
              fields="scoring")
   dj_entity_aggregate(entity="track_features", operation="count",
                    filters={{"track_id__in": pool_ids, "mood": "{style}"}})
   — if pure '{style}' is too thin for {length} tracks, widen to the neighbour
     moods listed above (NOT beyond — a peak_time intruder breaks a dub set).
   For a large source playlist, do staged narrowing before pair scoring:
   hard filters -> style/feature filters -> diversity cap -> final subset.
   Do not feed the whole crate to sequence_optimize.

5. Order for sustained character under the template arc:
   dj_sequence_optimize(track_ids=[...], algorithm="ga", template="{template}")
   — alternate texture (bright vs dark, busy vs sparse) so equal energy never
     reads as flat. Pin a strong opener and a strong closer in-style.
   For raw/hypnotic or low key_confidence material, prefer groove-first
   decisions: BPM, low-end, energy and percussion continuity can outweigh
   Camelot neatness.

6. Persist + verify it stays in character:
   dj_entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "style_{style}"}})
   local://sets/{{set_id}}/narrative — one coherent '{style}' mood, not a
   genre rollercoaster; local://sets/{{set_id}}/review — clean transitions.
   dj_ui_library_audit(playlist_id={playlist_id}) — subgenre mix of the source.

7. If the GA pulls in an off-style track to fix a transition, exclude it and
   re-run, or bridge via fix_transition_workflow.
   Do not promise delivery readiness until audio_file / physical MP3 exists.

Return: {{"playlist_id": {playlist_id}, "style": "{style}",
         "template": "{template}", "set_id": ..., "version_id": ...,
         "quality_score": ...}}.
"""


@prompt(
    name="style_lock_set_workflow",
    description="Build a mono-genre set locked to one subgenre/style band (e.g. all dub_techno).",
    tags={"namespace:workflow", "set_building", "style"},
    meta=PROMPT_META,
)
def style_lock_set_workflow(
    playlist_id: int,
    style: str = "hypnotic",
    length: int = 12,
) -> PromptResult:
    template = _STYLES.get(style, _STYLES["hypnotic"])[1]
    return PromptResult(
        messages=[Message(_body(playlist_id, style, length))],
        description=f"Style-locked '{style}' set ({template}) from playlist {playlist_id}.",
    )
