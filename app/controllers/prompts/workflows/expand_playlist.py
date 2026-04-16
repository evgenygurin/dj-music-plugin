"""Workflow prompt — split from monolithic workflows.py (Phase 10)."""

from typing import Annotated

from fastmcp.prompts import PromptResult, prompt
from pydantic import Field

from app.controllers.prompts.workflow_shared import (
    WORKFLOW_PROMPT_VERSION,
    make_prompt_result,
    message_assistant,
    message_user,
)


@prompt(
    name="expand_playlist_workflow",
    title="Expand Playlist",
    description="Discover and add similar tracks to a playlist from Yandex Music",
    tags={"discovery", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 7},
)
def expand_playlist_workflow(
    playlist_name: Annotated[str, Field(description="Playlist name or ID to expand")],
    target_count: Annotated[int, Field(description="Target number of tracks in playlist")] = 100,
) -> PromptResult:
    """Guide through expanding a playlist with similar tracks.

    Steps: Audit -> Find similar -> Import -> Download -> Analyze -> Re-audit -> Classify

    Args:
        playlist_name: Name or ID of playlist to expand
        target_count: Target number of tracks
    """
    return make_prompt_result(
        [
            message_user(
                f"""Expand playlist "{playlist_name}" to approximately {target_count} tracks
by discovering and adding similar music from Yandex Music.

Prerequisites: `unlock_tools(category="discovery")` if discovery tools are locked.

Follow these steps:

1. **Initial Audit**: `audit_playlist(playlist_query="{playlist_name}")` to understand
   current distribution (moods, BPM range, energy levels)
2. **Find Similar**: For each track or underrepresented mood:
   - `find_similar_tracks(track_id=<seed>, strategy="ym", limit=20)` — YM recommendations
   - Or `find_similar_tracks(track_id=<seed>, strategy="llm",
     search_queries=["..."])` — client-driven LLM discovery (no API key needed)
   - Filter by BPM compatibility and Camelot key compatibility
3. **Import**: `import_tracks(track_refs=[<ym_ids>], playlist_id=<id>)` to add to playlist
4. **Download**: `download_tracks(track_refs=[<ym_ids>])` to get MP3 files locally
5. **Verify Analysis**: `get_track_features(id=<track_id>)` for each new track
   - If missing features: `unlock_tools(category="audio")` then
     `analyze_track(track_id=<id>)` to extract audio features
6. **Re-audit**: `audit_playlist(playlist_query="{playlist_name}")` again to verify
   the expansion improved coverage
7. **Classify**: `classify_mood(playlist_id=<id>)` to assign subgenres to new tracks

Report progress after each step: similar tracks found, imported count, coverage changes."""
            ),
            message_assistant(
                f'Expanding "{playlist_name}" to ~{target_count} tracks. '
                f'Step 1: `audit_playlist(playlist_query="{playlist_name}")`...',
            ),
        ],
        description=f"Expand playlist '{playlist_name}' to {target_count} tracks",
    )
