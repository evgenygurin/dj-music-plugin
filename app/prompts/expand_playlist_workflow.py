"""expand_playlist_workflow — audit -> discover -> import -> analyze -> classify."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, target_count: int) -> str:
    return f"""To expand playlist {playlist_id} to ~{target_count} tracks:

1. Audit current state:
   local://playlists/{playlist_id}/audit — count pass/fail.
   local://playlists/{playlist_id}?include_tracks=true — current track IDs.

2. For each failing track, optionally remove or keep flagged.

3. Pick 3-5 seed tracks (high-quality, diverse mood from audit pass list).

4. Discover similar tracks per seed:
   provider_search(query=<seed title/artist>, type='tracks', limit=20)
   OR
   provider_read(entity='similar_tracks', id=<provider_track_id>, params={{'limit': 20}})

5. Filter candidates against feedback memory (if available):
   - Skip tracks already on entity_list(entity='track_feedback', filters={{'banned': True}})

6. Import new provider tracks that aren't in the library yet:
   entity_create(entity='track', data={{'provider': 'yandex', 'provider_ids': [...]}})
   — handler fetches metadata + creates rows + links playlist.

7. Download MP3s for newly-imported tracks:
   entity_create(entity='audio_file', data={{'track_ids': [...]}})
   — handler downloads + writes file + registers DjLibraryItem.

8. Analyze all newly-downloaded tracks at L3:
   entity_create(entity='track_features', data={{'track_ids': [...], 'level': 3}})

9. Classify mood for everything:
   entity_update(entity='track_features', data={{'track_ids': [...], 'action': 'classify_mood'}})

10. Re-audit:
    local://playlists/{playlist_id}/audit — verify pass rate improved.

Return: {{"playlist_id": {playlist_id}, "added_tracks": N, "final_count": N}}.
"""


@prompt(
    name="expand_playlist_workflow",
    description="Recipe: grow a playlist via provider discovery + import + analyze.",
    tags={"namespace:workflow", "discovery"},
    meta=PROMPT_META,
)
def expand_playlist_workflow(playlist_id: int, target_count: int = 100) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, target_count))],
        description=f"Recipe: expand playlist {playlist_id} toward {target_count} tracks.",
    )
