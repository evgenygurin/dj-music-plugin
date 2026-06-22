"""crate_digging_workflow — discovery-first deep digging + curation."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(seed: str, target_count: int, playlist_id: int | None) -> str:
    append_clause = (
        f"pass 'playlist_id': {playlist_id} so imports auto-append to it"
        if playlist_id is not None
        else "omit playlist_id to import into the library without attaching"
    )
    return f"""Dig for new techno around '{seed}' and curate ~{target_count} keepers.

Digging is selection, not collection — favour character over quantity.

1. Cast a wide net from the seed (artist, label, or vibe):
   provider_search(provider="yandex", query="{seed}", type="tracks", limit=20)
   provider_search(provider="yandex", query="{seed}", type="artists", limit=10)
   — note promising artist ids and a few seed track ids.

2. Follow the graph for depth:
   provider_read(provider="yandex", entity="track_similar", id=<seed_track_id>,
                params={{"limit": 20}})
   provider_read(provider="yandex", entity="artist_tracks", id=<artist_id>,
                params={{"page": 0, "page-size": 30}})
   — similar-track and artist-discography crawling surfaces deep cuts that
     text search misses.

3. De-duplicate against what you already have and against rejects:
   - skip ids already present: entity_list(entity="track", filters={{...}}).
   - skip banned: entity_list(entity="track_feedback", filters={{"status": "banned"}}).
   - consult prior chemistry: entity_list(entity="track_affinity",
     filters={{"net_sentiment__lt": 0}}) to avoid known-bad pairings later.

4. Import the survivors (idempotent by source+external_id):
   entity_create(entity="track", data={{"source": "yandex",
                "external_ids": [...]}})
   — {append_clause}.

5. Analyze imports so they become mixable (mood classification included):
   entity_create(entity="track_features", data={{"track_ids": [...], "level": 3}})

6. Curate down to ~{target_count}: read local://tracks/{{id}}/audit for each;
   drop hard-fail tracks; keep a diverse spread across the energy axis (don't
   end up with 30 peak-time bangers and no warm-up material).

7. Optionally seed taste memory for the keepers you love:
   entity_create(entity="track_feedback", data={{"track_id": <id>,
                "status": "liked", "rating": 5}})

Return: {{"seed": "{seed}", "discovered": N, "imported": N, "kept": N,
         "energy_spread": {{...mood: count...}}}}.
"""


@prompt(
    name="crate_digging_workflow",
    description="Discovery-first crate digging: search + similar/artist crawl, import, curate.",
    tags={"namespace:workflow", "discovery", "curation"},
    meta=PROMPT_META,
)
def crate_digging_workflow(
    seed: str,
    target_count: int = 20,
    playlist_id: int | None = None,
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(seed, target_count, playlist_id))],
        description=f"Crate-dig around '{seed}' for ~{target_count} keepers.",
    )
