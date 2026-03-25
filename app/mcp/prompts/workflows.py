"""Workflow prompt templates for multi-step DJ operations.

These prompts guide Claude through complex workflows by providing
structured conversation starters with context and instructions.
"""

from fastmcp.prompts import Message, prompt


@prompt
def build_set_workflow(
    playlist_name: str,
    template: str = "classic_60",
    duration_min: int = 60,
) -> list[Message]:
    """Guide through building a DJ set from scratch.

    Steps: Get playlist → Audit → Fill gaps → Build → Review → Fix → Deliver

    Args:
        playlist_name: Name or ID of source playlist
        template: Set template name (classic_60, peak_hour_60, etc.)
        duration_min: Target duration in minutes
    """
    return [
        Message(
            f"""Build a DJ set from playlist "{playlist_name}" using the "{template}" template
with target duration {duration_min} minutes.

Please follow these steps:

1. **Get Playlist**: Use `get_playlist` to retrieve "{playlist_name}"
2. **Audit Playlist**: Use `audit_playlist` to check track quality and coverage
3. **Fill Gaps**: If audit shows missing moods/energy levels, use `find_similar_tracks`
   to discover tracks that fill the gaps
4. **Build Set**: Use `build_set` with:
   - playlist_name: "{playlist_name}"
   - template: "{template}"
   - target_duration_min: {duration_min}
   - algorithm: "genetic" (for quality) or "greedy" (for speed)
5. **Review**: Use `quick_set_review` to analyze the generated set
6. **Fix Problems**: If review shows weak transitions:
   - Use `explain_transition` to understand why transitions are weak
   - Use `find_replacement` to get better alternatives
   - Use `rebuild_set` with pinned/excluded tracks
7. **Deliver**: When satisfied, use `deliver_set_workflow` prompt

Report progress and findings after each step."""
        ),
        Message(
            "I'll help you build this DJ set. Starting with retrieving the playlist...",
            role="assistant",
        ),
    ]


@prompt
def expand_playlist_workflow(
    playlist_name: str,
    target_count: int = 100,
) -> list[Message]:
    """Guide through expanding a playlist with similar tracks.

    Steps: Audit → Find similar → Import → Download → Analyze → Re-audit

    Args:
        playlist_name: Name or ID of playlist to expand
        target_count: Target number of tracks
    """
    return [
        Message(
            f"""Expand playlist "{playlist_name}" to approximately {target_count} tracks
by discovering and adding similar music from Yandex Music.

Please follow these steps:

1. **Initial Audit**: Use `audit_playlist` on "{playlist_name}" to understand
   current distribution (moods, BPM range, energy levels)
2. **Find Similar**: For each track or underrepresented mood:
   - Use `find_similar_tracks` with strategy="combined" (YM API + embeddings)
   - Filter by BPM compatibility and key compatibility
3. **Import**: Use `import_tracks` to add YM tracks to the playlist
   - Set auto_analyze=True for automatic audio feature extraction
4. **Download**: Use `download_tracks` to get MP3 files locally
5. **Verify Analysis**: Check that all new tracks have audio features via `get_track_features`
   - If missing, use `analyze_track` to extract features
6. **Re-audit**: Run `audit_playlist` again to verify the expansion improved coverage
7. **Classify**: Use `classify_mood` to assign subgenres to new tracks

Report progress and key findings (how many similar tracks found, coverage improvements,
any gaps remaining) after each step."""
        ),
        Message(
            f"I'll help you expand this playlist to ~{target_count} tracks. "
            "Let me start by auditing the current state...",
            role="assistant",
        ),
    ]


@prompt
def improve_set_workflow(
    set_name: str,
) -> list[Message]:
    """Guide through improving an existing DJ set.

    Steps: Review → Explain weak transitions → Find replacements → Rebuild → Compare

    Args:
        set_name: Name or ID of the set to improve
    """
    return [
        Message(
            f"""Improve the quality of DJ set "{set_name}" by identifying and fixing
weak transitions.

Please follow these steps:

1. **Review**: Use `quick_set_review` on "{set_name}" to get:
   - Overall transition quality score
   - Hard conflicts (score = 0.0)
   - Weak transitions (score < 0.5)
   - Problem areas (sudden energy jumps, key clashes, BPM mismatches)

2. **Explain Problems**: For each weak transition identified:
   - Use `explain_transition` to understand the specific issues
   - Note: BPM distance, key compatibility, energy step, timbral mismatch, etc.

3. **Find Replacements**: For problematic tracks:
   - Use `find_replacement` at that position
   - This scores candidates against BOTH neighbors
   - Review top 3-5 suggestions with their combined scores

4. **Rebuild**: Use `rebuild_set` with:
   - pin_tracks: Keep the good transitions (high-scoring pairs)
   - exclude_tracks: Remove problematic tracks
   - include_tracks: Force-include the replacements you selected
   - algorithm: "genetic" for thorough optimization

5. **Compare**: Use `compare_set_versions` to verify improvement:
   - Check if overall score increased
   - Verify weak transitions were fixed
   - Ensure no new problems were introduced

6. **Iterate**: If problems remain, repeat steps 2-5 focusing on remaining weak spots

Report score improvements and specific transition fixes after each rebuild."""
        ),
        Message(
            f'I\'ll help you improve "{set_name}". Starting with a quality review...',
            role="assistant",
        ),
    ]


@prompt
def deliver_set_workflow(
    set_name: str,
    sync_ym: bool = False,
) -> list[Message]:
    """Guide through delivering a completed DJ set.

    Steps: Score → Handle conflicts → Export → Copy files → YM sync

    Args:
        set_name: Name or ID of the set to deliver
        sync_ym: Whether to sync to Yandex Music playlist
    """
    sync_note = "\n7. **YM Sync**: Push the set to Yandex Music as a playlist" if sync_ym else ""

    return [
        Message(
            f"""Deliver the completed DJ set "{set_name}" with all export formats
and optional Yandex Music sync.

Please follow these steps:

1. **Score All Transitions**: Use `score_transitions` with mode="set" to:
   - Calculate all consecutive pair scores
   - Identify any hard conflicts (score = 0.0)
   - Get overall quality metrics (avg, min, weak count)

2. **Handle Conflicts**: If hard conflicts exist:
   - Use `explain_transition` on each conflicting pair
   - Either: use `find_replacement` to fix them
   - Or: continue with conflicts if user accepts

3. **Deliver**: Use `deliver_set` with:
   - set_name: "{set_name}"
   - copy_files: True (numbered MP3s)
   - sync_to_ym: {sync_ym}
   - formats: ["m3u8", "json_guide", "cheat_sheet"]
   - Handle any elicitation (conflict warnings, YM playlist exists, etc.)

4. **Verify Exports**: Check that all files were created in generated-sets/:
   - Numbered MP3 files (01. Track.mp3, 02. Track.mp3, ...)
   - M3U8 playlist with DJ extension tags (BPM, key, cue points, transitions)
   - JSON guide (detailed per-track and per-transition info)
   - Text cheat sheet (human-readable transition notes)

5. **Check iCloud**: Report any iCloud stub warnings (files not downloaded)
   - Note which tracks need manual download from iCloud

6. **Get Cheat Sheet**: Use `get_set_cheat_sheet` for quick DJ reference
   - Shows transition types, scores, BPM/key changes, flagged problems{sync_note}

The set is ready for import into your DJ software (Traktor, Rekordbox, djay).
Report the output directory path and any warnings."""
        ),
        Message(
            f'I\'ll help you deliver "{set_name}". '
            f"{'This will include syncing to Yandex Music. ' if sync_ym else ''}"
            "Let me start by scoring all transitions...",
            role="assistant",
        ),
    ]


@prompt
def full_expansion_pipeline(
    source_playlist: str,
    target_per_subgenre: int = 50,
) -> list[Message]:
    """Guide through complete playlist expansion and distribution pipeline.

    Steps: Audit → Discover → Import → Download → Analyze → Classify → Distribute

    Args:
        source_playlist: Source playlist name (e.g., "TECHNO FOR DJ SETS")
        target_per_subgenre: Target tracks per subgenre playlist
    """
    return [
        Message(
            f"""Execute the complete pipeline to expand "{source_playlist}" and
distribute tracks across all 15 techno subgenre playlists with ~{target_per_subgenre}
tracks each.

Please follow these steps:

1. **Initial Audit**: Use `audit_playlist` on "{source_playlist}"
   - Check current mood distribution
   - Identify underrepresented subgenres
   - Note BPM and energy coverage

2. **Discover Similar**: For each underrepresented subgenre:
   - Pick 3-5 representative tracks from that subgenre
   - Use `find_similar_tracks` with strategy="combined"
   - Target: find {target_per_subgenre} candidates per subgenre
   - Filter by BPM (120-155) and key compatibility

3. **Import**: Use `import_tracks` in batches:
   - Set auto_analyze=True for automatic feature extraction
   - Add to "{source_playlist}"
   - Report success/failure counts

4. **Download**: Use `download_tracks` for all newly imported tracks
   - Skip tracks already downloaded
   - Report iCloud stub warnings

5. **Analyze**: Verify all tracks have audio features:
   - Use `get_library_stats` to check feature coverage
   - For any missing features, use `analyze_batch`
   - Wait for analysis completion (can take 2-10 min per track)

6. **Re-audit**: Run `audit_playlist` again on "{source_playlist}"
   - Verify all 15 subgenres are represented
   - Check that distribution is more balanced
   - Confirm BPM and energy coverage improved

7. **Classify All**: Use `classify_mood` with reclassify=True
   - This assigns each track to one of 15 subgenres
   - Reports confidence scores and reasoning

8. **Distribute**: Use `distribute_to_subgenres` with:
   - source_playlist: "{source_playlist}"
   - mode: "clean_rebuild" (clears and repopulates all subgenre playlists)
   - sync_to_ym: True (pushes to YM playlists)
   - This creates/updates 15 playlists: ambient_dub, dub_techno, minimal, ..., hard_techno

9. **Verify**: Check distribution results:
   - Each subgenre playlist should have ~{target_per_subgenre} tracks
   - Use `get_library_stats` to see final distribution
   - Note any subgenres still under-represented

Report progress, counts, and any issues after each major step.
This is a long-running pipeline (1-3 hours for 1000+ tracks)."""
        ),
        Message(
            f'I\'ll execute the full expansion pipeline for "{source_playlist}". '
            f"Target: {target_per_subgenre} tracks per subgenre. "
            "This will take significant time. Starting with initial audit...",
            role="assistant",
        ),
    ]
