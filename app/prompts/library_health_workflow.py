"""library_health_workflow — full library health & coverage report."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int | None) -> str:
    scope = (
        f"scoped to playlist {playlist_id} (track / track_features have no "
        "playlist_id column: first resolve the playlist's track ids via "
        f"local://playlists/{playlist_id}?include_tracks=true, then scope every "
        'aggregate below with filters={"track_id__in": pool_ids} on '
        'track_features and filters={"id__in": pool_ids} on track)'
        if playlist_id is not None
        else "across the whole library"
    )
    audit_uri = (
        f"local://playlists/{playlist_id}/audit"
        if playlist_id is not None
        else "local://playlists/<each playlist>/audit"
    )
    return f"""Produce a health report {scope}.

1. Headline counts:
   dj_entity_aggregate(entity="track", operation="count")
   dj_entity_aggregate(entity="track_features", operation="count")
   — coverage = features / tracks. Below ~95% means analysis backlog.

2. Analysis-level coverage (how deep is the library analyzed):
   dj_entity_aggregate(entity="track_features", operation="histogram",
                    field="analysis_level")
   — flag the share at level < 3 (not yet set-ready).

3. Tempo distribution:
   dj_entity_aggregate(entity="track_features", operation="histogram", field="bpm")
   — techno core is 120-150; note clusters and outliers (<118 / >155).

4. Harmonic distribution:
   dj_entity_aggregate(entity="track_features", operation="histogram",
                    field="key_code")
   — read reference://camelot to map key_code -> Camelot; spot thin keys
     (mixing dead-ends) and over-represented keys.

5. Subgenre (mood) distribution:
   dj_entity_aggregate(entity="track_features", operation="distinct", field="mood")
   then per mood:
   dj_entity_aggregate(entity="track_features", operation="count",
                    filters={{"mood": <m>}})
   — check the energy axis (ambient_dub .. hard_techno) for gaps.

6. Quality flags — sweep audits:
   {audit_uri} — tally pass/fail and the top failing rules
   (bpm_out_of_range, lufs_out_of_range, clipping_risk, unreliable_bpm,
    variable_tempo). Cross-check thresholds via reference://audit_rules.

7. Physical-file readiness:
   dj_entity_aggregate(entity="audio_file", operation="count")
   — vs track count; low ratio means most tracks have no local MP3
     (downloaded only on demand under deliver_set_workflow).

8. Visual rollup (Prefab clients):
   dj_ui_library_dashboard()   — BPM / mood / Camelot at a glance.
   dj_ui_library_audit(playlist_id={playlist_id if playlist_id is not None else 0})

Return: {{"tracks": N, "feature_coverage": 0.xx, "level_lt_3": N,
         "bpm_clusters": [...], "thin_keys": [...], "subgenre_gaps": [...],
         "audit_fail_top": [...], "audio_file_ratio": 0.xx,
         "recommendations": [...]}}.
"""


@prompt(
    name="library_health_workflow",
    description="Library-wide health report: coverage, BPM/key/mood spread, audit fails.",
    tags={"namespace:workflow", "audit", "library"},
    meta=PROMPT_META,
)
def library_health_workflow(playlist_id: int | None = None) -> PromptResult:
    target = f"playlist {playlist_id}" if playlist_id is not None else "whole library"
    return PromptResult(
        messages=[Message(_body(playlist_id))],
        description=f"Library health report ({target}).",
    )
