"""deliver_set_workflow — export + (optional) YM sync."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _build_body(set_id: int, sync_to_ym: bool) -> str:
    sync_clause = (
        "7. Sync the set to the platform as a new playlist (there is no\n"
        "   single 'create from set' operation — do it in two real steps):\n"
        "   a. Create the empty playlist:\n"
        "      provider_write(entity='playlist', operation='create',\n"
        "                    params={'title': '<set name>'})  -> new playlist id.\n"
        "   b. Resolve each set track's Yandex id (yandex_track_id via\n"
        "      entity_get(entity='track', id=<tid>) / its external ids), then:\n"
        "      provider_write(entity='playlist', operation='add_tracks',\n"
        "                    params={'playlist_id': <new id>,\n"
        "                            'track_ids': [<yandex ids in set order>],\n"
        "                            'at': 0})\n"
        "   ('at' = current trackCount: 0 for a fresh playlist; for an\n"
        "    APPEND pass the existing trackCount, else YM PREPENDS to 0.\n"
        "    The track_ids ARE the per-track yandex external ids — the\n"
        "    same ids the audio_file download resolved; the `track` view\n"
        "    does not expose yandex_track_id directly. Verify final order\n"
        "    with provider_read(entity='playlist', id=<new id>).)\n"
        "   (Alternatively run the playlist_sync_workflow prompt with\n"
        "    direction='push' once the local playlist mirrors the set.)\n"
        if sync_to_ym
        else "7. Skip platform sync (sync_to_ym=false).\n"
    )
    continuous_clause = (
        "   Also include the continuous beatmatched mix if one was rendered:\n"
        "   render_set_workflow produces generated-sets/render/v<version_id>/MIX.mp3.\n"
        "   Copy it into the deliverable bundle when DeliverySettings\n"
        "   emit_continuous_mix is enabled (default).\n"
    )
    return f"""To deliver set {set_id}:

0. Finalize audio quality FIRST (L5-before-delivery): bring every set
   track to analysis_level=5 so the picker routes Neural-Mix presets on
   accurate spectral / pitch features (303 vs vocal, DRUM_SWAP vs
   ECHO_OUT). Skip tracks already at L5.
   a. Download MP3s — entity_create(entity='audio_file',
      data={{'track_ids': [<set track ids>]}}). Batch 3-5 ids per call:
      a larger batch can exceed the 120s tool timeout and roll back the
      DB registration (files land on disk but no library_item row). L5
      reanalyze NEEDS that row.
   b. L5 each track — entity_update(entity='track_features',
      id=<track_id>, data={{'level': 5}}) (fast, ~5-10s; requires the
      audio_file from step a, else 'audio_file not found').
   c. Re-build so transitions re-score on L5 features —
      entity_create(entity='set_version', data={{'set_id': {set_id},
      'label': 'L5 final', 'track_order': [<same order>]}}).

1. Read the latest version summary:
   local://sets/{set_id}/summary — note version_id and quality_score.

2. Score every transition fresh (read-only, not cached):
   transition_score_pool(track_ids=<ordered track list>)
   — returns a live NxN score matrix for inspection / QA only; it does
     NOT write to the ``transitions`` table.
   Persisted transition rows are refreshed by step 0c when you rebuild
   the set_version on top of L5 features.

3. Review for hard conflicts:
   local://sets/{set_id}/review — inspect 'hard_conflicts'.

4. If hard_conflicts is non-empty:
   - Use ctx.elicit to ask the user whether to continue or abort.
   - If abort -> stop; if continue -> proceed.

5. Capture deliverables (server-side delivery handler is not yet wired
   on the v1 surface — the LLM assembles the artefacts itself from
   existing resources):
   - local://sets/{set_id}/full — JSON guide (set_summary + tracks +
     transitions, ready to drop into a `.json` artefact next to the MP3s).
   - local://sets/{set_id}/cheatsheet — DJ-booth cheat sheet (BPM/key/
     energy per slot); copy verbatim into a `.txt` next to the MP3s.
   - local://sets/{set_id}/tracks — ordered (track_id, title, position)
     list; assemble M3U8 / Rekordbox XML client-side from this plus the
     ``audio_file`` rows fetched via entity_get(entity='audio_file', ...).

6. Copy MP3 files into generated-sets/<name>/ — resolve each track's
   audio_file via entity_list(entity='audio_file', filters={{
   'track_id__in': [<set track ids>]}}, fields='full') to get
   `file_path`, then ``cp`` to the destination.
{continuous_clause}
{sync_clause}
8. Final verification:
   - local://sets/{set_id}/summary (version count increased? quality_score stable?)
   - If any export failed, report file_path=null + error for that format.

Return: {{"set_id": {set_id}, "exports": [...], "ym_playlist_id": ...}}.
"""


@prompt(
    name="deliver_set_workflow",
    description="Recipe: export a set (+ optional YM sync) with a conflict gate.",
    tags={"namespace:workflow", "delivery"},
    meta=PROMPT_META,
)
def deliver_set_workflow(set_id: int, sync_to_ym: bool = False) -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(set_id, sync_to_ym))],
        description=f"Recipe: deliver set {set_id} (sync_to_ym={sync_to_ym}).",
    )
