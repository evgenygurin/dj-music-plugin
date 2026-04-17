"""Workflow prompt — split from monolithic workflows.py (Phase 10)."""

from typing import Annotated

from fastmcp.prompts import PromptResult, prompt
from pydantic import Field

from app.controllers.prompts.workflow_shared import (
    TRANSITION_SCORING_AND_SEARCH_GUIDE,
    WORKFLOW_PROMPT_VERSION,
    make_prompt_result,
    message_assistant,
    message_user,
)


@prompt(
    name="full_expansion_pipeline",
    title="Full Expansion Pipeline",
    description="Full pipeline: audit, discover, import, analyze, classify, distribute",
    tags={"curation", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 9},
)
def full_expansion_pipeline(
    source_playlist: Annotated[
        str, Field(description='Source playlist name (e.g., "TECHNO FOR DJ SETS")')
    ],
    target_per_subgenre: Annotated[
        int, Field(description="Target tracks per subgenre playlist (15 subgenres total)")
    ] = 50,
) -> PromptResult:
    """Guide through complete playlist expansion and distribution pipeline.

    Steps: Audit -> Discover -> Import -> Download -> Analyze -> Classify -> Distribute

    Args:
        source_playlist: Source playlist name (e.g., "TECHNO FOR DJ SETS")
        target_per_subgenre: Target tracks per subgenre playlist
    """
    return make_prompt_result(
        [
            message_user(
                f"""Execute the complete pipeline to expand "{source_playlist}" and
distribute tracks across all 15 techno subgenre playlists with ~{target_per_subgenre}
tracks each.

Prerequisites:
- `unlock_tools(category="discovery")` for discovery tools
- `unlock_tools(category="curation")` for curation tools
- `unlock_tools(category="audio")` for audio analysis (step 5)

Follow these steps:

1. **Initial Audit**: `audit_playlist(playlist_query="{source_playlist}")`:
   - Check current mood distribution
   - Identify underrepresented subgenres
   - Note BPM and energy coverage

2. **Discover Similar**: For each underrepresented subgenre:
   - Pick 3-5 representative tracks from that subgenre
   - `find_similar_tracks(track_id=<seed>, strategy="ym", limit=20)` per seed
   - Target: find {target_per_subgenre} candidates per subgenre
   - Filter by BPM (120-155) and Camelot key compatibility

3. **Import**: `import_tracks(track_refs=[<ym_ids>], playlist_id=<id>)` in batches:
   - Report success/failure counts after each batch

4. **Download**: `download_tracks(track_refs=[<ym_ids>])` for all newly imported tracks
   - Skip tracks already downloaded
   - Report iCloud stub warnings

5. **Analyze**: Verify all tracks have audio features:
   - `get_library_stats()` to check feature coverage
   - For missing features: `analyze_track(track_id=<id>)` per track
   - Analysis takes 2-10 min per track — report progress

6. **Re-audit**: `audit_playlist(playlist_query="{source_playlist}")` again:
   - Verify all 15 subgenres are represented
   - Check that distribution is more balanced
   - Confirm BPM and energy coverage improved

7. **Classify All**: `classify_mood(playlist_id=<id>, reclassify=True)`:
   - Assigns each track to one of 15 subgenres
   - Reports confidence scores and reasoning

8. **Distribute**: `distribute_to_subgenres(source_playlist_id=<id>,
   mode="clean_rebuild", sync_to_ym=True)`:
   - Clears and repopulates all 15 subgenre playlists
   - Pushes to YM playlists: ambient_dub, dub_techno, ..., hard_techno

9. **Verify**: `get_library_stats()` to see final distribution:
   - Each subgenre playlist should have ~{target_per_subgenre} tracks
   - Note any subgenres still under-represented

Report progress, counts, and any issues after each major step.
This is a long-running pipeline (1-3 hours for 1000+ tracks).

Optional (after you build or edit DJ sets): use persisted transition tools — reference:
"""
                + "\n"
                + TRANSITION_SCORING_AND_SEARCH_GUIDE
            ),
            message_assistant(
                f'Executing full expansion pipeline for "{source_playlist}". '
                f"Target: {target_per_subgenre} tracks per subgenre (15 subgenres). "
                f'Step 1: `audit_playlist(playlist_query="{source_playlist}")`...',
            ),
        ],
        description=(
            f"Full expansion pipeline for '{source_playlist}' ({target_per_subgenre} per subgenre)"
        ),
    )
