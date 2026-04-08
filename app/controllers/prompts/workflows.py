"""Workflow prompt templates for multi-step DJ operations.

These prompts guide Claude through complex workflows by providing
structured conversation starters with context and instructions.

Each prompt follows the pattern:
- @prompt(name, description, tags, meta) for MCP discovery metadata
- Field(description=...) for parameter documentation in prompts/list
- User message with numbered steps referencing real tool names
- Assistant message priming the first concrete action
"""

from __future__ import annotations

from typing import Annotated

from fastmcp.prompts import Message, prompt
from pydantic import Field


@prompt(
    name="build_set_workflow",
    title="Build DJ Set",
    description="Step-by-step: build an optimized DJ set from a playlist",
    tags={"sets", "workflow"},
    meta={"version": "1.1", "steps": 7},
)
def build_set_workflow(
    playlist_name: Annotated[str, Field(description="Playlist name or ID to build set from")],
    template: Annotated[
        str,
        Field(
            description=(
                "Set template: classic_60, peak_hour_60, roller_90,"
                " progressive_120, wave_120, closing_60"
            ),
        ),
    ] = "classic_60",
    duration_min: Annotated[int, Field(description="Target set duration in minutes")] = 60,
) -> list[Message]:
    """Guide through building a DJ set from scratch.

    Steps: Get playlist -> Audit -> Fill gaps -> Build -> Review -> Fix -> Deliver

    Args:
        playlist_name: Playlist name or ID to build set from
        template: Set template name (classic_60, peak_hour_60, etc.)
        duration_min: Target duration in minutes
    """
    return [
        Message(
            f"""Build a DJ set from playlist "{playlist_name}" using the "{template}" template
with target duration {duration_min} minutes.

Follow these steps:

1. **Get Playlist**: `get_playlist(query="{playlist_name}", include_tracks=True)`
2. **Audit Playlist**: `audit_playlist(playlist_query="{playlist_name}")` to check
   track quality, mood distribution, BPM range, and energy coverage
3. **Fill Gaps**: If audit shows missing moods/energy levels:
   - `find_similar_tracks(track_id=<seed>, strategy="ym")` for each gap
   - Or use `llm_discovery_workflow` prompt for LLM-assisted discovery
4. **Build Set**: `build_set(playlist_id=<id>, name="...", template="{template}",
   algorithm="ga")` — use "greedy" for speed, "ga" for quality
5. **Review**: `quick_set_review(set_id=<id>)` to analyze transitions and energy arc
6. **Fix Problems**: If review shows weak transitions (score < 0.5):
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)` for each weak pair
   - `find_replacement(set_id=<id>, position=<pos>)` for alternatives
   - `rebuild_set(set_id=<id>, pin=<good>, exclude=<bad>, algorithm="ga")`
7. **Deliver**: When satisfied, use `deliver_set` tool or `deliver_set_workflow` prompt

Report progress and findings after each step."""
        ),
        Message(
            f'Building DJ set from "{playlist_name}" ({template}, {duration_min} min). '
            f'Step 1: `get_playlist(query="{playlist_name}", include_tracks=True)`...',
            role="assistant",
        ),
    ]


@prompt(
    name="expand_playlist_workflow",
    title="Expand Playlist",
    description="Discover and add similar tracks to a playlist from Yandex Music",
    tags={"discovery", "workflow"},
    meta={"version": "1.1", "steps": 7},
)
def expand_playlist_workflow(
    playlist_name: Annotated[str, Field(description="Playlist name or ID to expand")],
    target_count: Annotated[int, Field(description="Target number of tracks in playlist")] = 100,
) -> list[Message]:
    """Guide through expanding a playlist with similar tracks.

    Steps: Audit -> Find similar -> Import -> Download -> Analyze -> Re-audit -> Classify

    Args:
        playlist_name: Name or ID of playlist to expand
        target_count: Target number of tracks
    """
    return [
        Message(
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
        Message(
            f'Expanding "{playlist_name}" to ~{target_count} tracks. '
            f'Step 1: `audit_playlist(playlist_query="{playlist_name}")`...',
            role="assistant",
        ),
    ]


@prompt(
    name="improve_set_workflow",
    title="Improve DJ Set",
    description="Identify and fix weak transitions in an existing DJ set",
    tags={"sets", "workflow"},
    meta={"version": "1.1", "steps": 6},
)
def improve_set_workflow(
    set_name: Annotated[str, Field(description="DJ set name or ID to improve")],
) -> list[Message]:
    """Guide through improving an existing DJ set.

    Steps: Review -> Explain weak transitions -> Find replacements -> Rebuild -> Compare -> Iterate

    Args:
        set_name: Name or ID of the set to improve
    """
    return [
        Message(
            f"""Improve the quality of DJ set "{set_name}" by identifying and fixing
weak transitions.

Follow these steps:

1. **Review**: `quick_set_review(set_id=<id>)` on "{set_name}" to get:
   - Overall transition quality score
   - Hard conflicts (score = 0.0) — BPM >10, Camelot >=5, or energy >6 LUFS
   - Weak transitions (score < 0.5)
   - Problem areas (sudden energy jumps, key clashes, BPM mismatches)

2. **Explain Problems**: For each weak transition:
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)`
   - Note which component failed: BPM, harmonic, energy, spectral, or groove

3. **Find Replacements**: For problematic tracks:
   - `find_replacement(set_id=<id>, position=<pos>, count=5)`
   - This scores candidates against BOTH neighbors
   - Review top 3-5 suggestions with their combined scores

4. **Rebuild**: `rebuild_set(set_id=<id>, pin=[<good_ids>], exclude=[<bad_ids>],
   algorithm="ga", version_label="improved")` with:
   - pin: tracks with high-scoring transitions (keep them)
   - exclude: problematic tracks (remove them)

5. **Compare**: `compare_set_versions(set_id=<id>)` to verify improvement:
   - Check if overall score increased
   - Verify weak transitions were fixed
   - Ensure no new problems were introduced

6. **Iterate**: If problems remain, repeat steps 2-5 focusing on remaining weak spots

Report score improvements and specific transition fixes after each rebuild."""
        ),
        Message(
            f'Improving "{set_name}". Step 1: `quick_set_review(set_id=<id>)`...',
            role="assistant",
        ),
    ]


@prompt(
    name="deliver_set_workflow",
    title="Deliver DJ Set",
    description="Export a completed DJ set: score, handle conflicts, generate files, YM sync",
    tags={"delivery", "workflow"},
    meta={"version": "1.1", "steps": 7},
)
def deliver_set_workflow(
    set_name: Annotated[str, Field(description="DJ set name or ID to deliver")],
    sync_ym: Annotated[
        bool, Field(description="Whether to sync set to Yandex Music playlist")
    ] = False,
) -> list[Message]:
    """Guide through delivering a completed DJ set.

    Steps: Score -> Handle conflicts -> Export -> Copy files -> Verify -> Cheat sheet -> YM sync

    Args:
        set_name: Name or ID of the set to deliver
        sync_ym: Whether to sync to Yandex Music playlist
    """
    sync_note = (
        "\n7. **YM Sync**: `push_set_to_ym(set_id=<id>)` to push the set as a YM playlist"
        if sync_ym
        else ""
    )

    return [
        Message(
            f"""Deliver the completed DJ set "{set_name}" with all export formats
and optional Yandex Music sync.

Prerequisites: `unlock_tools(category="delivery")` if delivery tools are locked.

Follow these steps:

1. **Score All Transitions**: `score_transitions(mode="set", set_id=<id>)` to:
   - Calculate all consecutive pair scores
   - Identify any hard conflicts (score = 0.0)
   - Get overall quality metrics (avg, min, weak count)

2. **Handle Conflicts**: If hard conflicts exist:
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)` on each conflicting pair
   - Either: `find_replacement(set_id=<id>, position=<pos>)` to fix them
   - Or: continue with conflicts if user accepts (elicitation will ask)

3. **Deliver**: `deliver_set(set_id=<id>, copy_files=True, sync_to_ym={sync_ym},
   formats=["m3u8", "json_guide", "cheat_sheet"])`:
   - Handle any elicitation prompts (conflict warnings, YM playlist exists, etc.)

4. **Verify Exports**: Check that all files were created in generated-sets/:
   - Numbered MP3 files (01. Track.mp3, 02. Track.mp3, ...)
   - M3U8 playlist with DJ extension tags (BPM, key, cue points, transitions)
   - JSON guide (detailed per-track and per-transition info)
   - Text cheat sheet (human-readable transition notes)

5. **Check iCloud**: Report any iCloud stub warnings (files not downloaded)
   - Note which tracks need manual download from iCloud

6. **Get Cheat Sheet**: `get_set_cheat_sheet(set_id=<id>)` for quick DJ reference
   - Shows transition types, scores, BPM/key changes, flagged problems{sync_note}

The set is ready for import into your DJ software (Traktor, Rekordbox, djay).
Report the output directory path and any warnings."""
        ),
        Message(
            f'Delivering "{set_name}". '
            f"{'Will sync to Yandex Music after export. ' if sync_ym else ''}"
            'Step 1: `score_transitions(mode="set", set_id=<id>)`...',
            role="assistant",
        ),
    ]


@prompt(
    name="full_expansion_pipeline",
    title="Full Expansion Pipeline",
    description="Full pipeline: audit, discover, import, analyze, classify, distribute",
    tags={"curation", "workflow"},
    meta={"version": "1.1", "steps": 9},
)
def full_expansion_pipeline(
    source_playlist: Annotated[
        str, Field(description='Source playlist name (e.g., "TECHNO FOR DJ SETS")')
    ],
    target_per_subgenre: Annotated[
        int, Field(description="Target tracks per subgenre playlist (15 subgenres total)")
    ] = 50,
) -> list[Message]:
    """Guide through complete playlist expansion and distribution pipeline.

    Steps: Audit -> Discover -> Import -> Download -> Analyze -> Classify -> Distribute

    Args:
        source_playlist: Source playlist name (e.g., "TECHNO FOR DJ SETS")
        target_per_subgenre: Target tracks per subgenre playlist
    """
    return [
        Message(
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
This is a long-running pipeline (1-3 hours for 1000+ tracks)."""
        ),
        Message(
            f'Executing full expansion pipeline for "{source_playlist}". '
            f"Target: {target_per_subgenre} tracks per subgenre (15 subgenres). "
            f'Step 1: `audit_playlist(playlist_query="{source_playlist}")`...',
            role="assistant",
        ),
    ]


@prompt(
    name="llm_discovery_workflow",
    title="LLM-Assisted Discovery",
    description="Client-driven discovery: Claude generates search queries, no API key needed",
    tags={"discovery", "workflow"},
    meta={"version": "1.0", "steps": 5, "requires_api_key": False},
)
def llm_discovery_workflow(
    track_name: Annotated[
        str, Field(description="Track title or 'Artist - Title' to find similar tracks for")
    ],
    track_id: Annotated[
        int | None, Field(description="Local DB track ID (if known, enables audio feature lookup)")
    ] = None,
    limit: Annotated[int, Field(description="How many similar tracks to find")] = 20,
) -> list[Message]:
    """Client-driven discovery: generate search queries and find similar tracks.

    Steps: Analyze track -> Generate queries -> Call find_similar_tracks -> Review -> Import

    For Claude Code MAX users (no API key needed). Claude generates search queries
    based on track characteristics, then passes them to find_similar_tracks.

    Args:
        track_name: Track title or artist + title
        track_id: Optional local DB track ID (if known)
        limit: How many similar tracks to find
    """
    id_instruction = ""
    if track_id:
        id_instruction = (
            f"\n   - `get_track(id={track_id})` and `get_track_features(id={track_id})` "
            "to get BPM, Camelot key, energy, mood"
        )

    return [
        Message(
            f"""Find {limit} tracks similar to "{track_name}" using client-driven discovery.

This workflow does NOT require an API key — you generate the search queries yourself.

Prerequisites: `unlock_tools(category="discovery")` if discovery tools are locked.

Follow these steps:

1. **Analyze the source track**:{id_instruction}
   - Identify key characteristics: BPM range, subgenre, mood, energy level, artists
   - Note the Camelot key for harmonic compatibility

2. **Generate search queries**: Based on the track's style, create 5-10 Yandex Music
   search queries. Mix these approaches:
   - Similar artists in the same subgenre
   - Subgenre + mood keywords (e.g. "dark minimal techno")
   - Labels known for this style (e.g. "Drumcode", "Mord", "Perc Trax")
   - BPM-adjacent styles (if source is 135 BPM, search 130-140 BPM range)

3. **Call find_similar_tracks** with your generated queries:
   ```
   find_similar_tracks(
       track_id={track_id or "<track_id>"},
       strategy="llm",
       search_queries=["query1", "query2", "query3", ...],
       limit={limit}
   )
   ```

4. **Review results**: Check if the similar tracks match the source track's vibe.
   If not enough results, generate more specific queries and call again.

5. **Import**: `import_tracks(track_refs=[<ym_ids>], playlist_id=<id>)` to add the
   best matches to the library.

This is the recommended workflow for Claude Code MAX subscribers (no API key needed)."""
        ),
        Message(
            f'Finding tracks similar to "{track_name}" via client-driven discovery. '
            f"Step 1: analyzing track characteristics"
            f"{f' — `get_track(id={track_id})`' if track_id else ''}...",
            role="assistant",
        ),
    ]
