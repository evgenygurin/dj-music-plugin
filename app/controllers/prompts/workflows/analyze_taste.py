"""Workflow prompt — taste profile analysis from YM likes/dislikes."""

from __future__ import annotations

from typing import Annotated

from fastmcp.prompts import Message, prompt
from pydantic import Field


@prompt(
    name="analyze_taste_workflow",
    title="Analyze Taste Profile",
    description=(
        "Deep analysis of YM liked/disliked tracks: feature patterns, "
        "subgenre preferences, BPM/energy sweet spots — produces a structured report."
    ),
    tags={"discovery", "workflow"},
    meta={"version": "1.0", "steps": 6},
)
def analyze_taste_workflow(
    focus: Annotated[
        str,
        Field(
            description=(
                "Analysis focus: 'full' (default), 'subgenres', 'bpm', 'energy', or 'transitions'"
            )
        ),
    ] = "full",
    playlist_query: Annotated[
        str | None,
        Field(
            description=(
                "Optional: restrict liked-track lookup to a specific playlist "
                "(e.g. 'TECHNO FOR DJ SETS'). Leave empty to use the full YM liked list."
            )
        ),
    ] = None,
) -> list[Message]:
    """Guide through a full taste-profile analysis using YM feedback + local audio features.

    Steps:
      1. Collect liked IDs from YM
      2. Identify disliked tracks in the local library
      3. Pull audio features for both sets
      4. Compare key dimensions (subgenre, BPM, energy, dissonance, danceability)
      5. Synthesise patterns
      6. Write a structured Markdown report

    Args:
        focus: Which dimensions to analyse in depth.
        playlist_query: Scope liked tracks to a named playlist.
    """
    playlist_instruction = (
        f'\n   - Scope to playlist "{playlist_query}" via '
        f'`search_library(query="{playlist_query}")` to get its track IDs first.'
        if playlist_query
        else ""
    )

    focus_hint = {
        "subgenres": (
            "Concentrate on subgenre distribution. "
            "Count how many liked vs disliked tracks belong to each of the 15 subgenres. "
            "Identify the top 3 preferred and top 3 avoided subgenres."
        ),
        "bpm": (
            "Concentrate on BPM. Compute avg, min, max, and p10/p90 for liked vs disliked. "
            "Identify the BPM sweet spot (range where liked:disliked ratio is highest)."
        ),
        "energy": (
            "Concentrate on energy (integrated_lufs). "
            "Compute distribution quartiles for liked vs disliked. "
            "Identify preferred loudness tier: quiet (<-14 LUFS),"
            " medium (-14 to -11), loud (>-11)."
        ),
        "transitions": (
            "Concentrate on what makes a good transition from a liked track. "
            "For each liked track note its key_code and bpm, then look for common Camelot "
            "clusters and BPM ranges. Summarise the most DJ-friendly key/BPM combinations."
        ),
        "full": (
            "Cover all dimensions: subgenre distribution, BPM range, energy tier, "
            "dissonance (harmonic tension), danceability, and mood. "
            "For each dimension compute liked vs disliked stats and note the delta."
        ),
    }.get(focus, "Cover all dimensions (subgenre, BPM, energy, dissonance, danceability, mood).")

    return [
        Message(
            f"""Analyse the user's taste profile from Yandex Music liked and disliked tracks,
then produce a structured Markdown report.

Focus: **{focus}**
{focus_hint}

Prerequisites:
- `unlock_tools(category="discovery")` — for `filter_by_feedback`, `find_similar_tracks`
- `unlock_tools(category="curation")` — for `get_library_stats`, `audit_playlist`

---

## Step 1 — Collect liked track IDs from YM

```
ym_likes(action="get_liked", limit=200, offset=0)
```
Paginate (increment `offset` by 200) until `truncated=False`.{playlist_instruction}
Store the full list as `liked_ids`.

---

## Step 2 — Identify disliked tracks in the local library

`filter_by_feedback` classifies any list of YM track IDs into liked / disliked / neutral.
Call it with all local track IDs that have a `ym_id`:

```
# First get local library track IDs
get_library_stats()            # to see total counts
search_library(query="", limit=500)   # repeat with offset to get all ym_ids
```

Then:
```
filter_by_feedback(track_ids=<all_local_ym_ids>)
```
Extract `disliked` bucket → `disliked_ids`.

**Note**: only tracks that are BOTH in the local DB and disliked on YM will appear.
This is a lower bound on dislikes; use it for feature comparison.

---

## Step 3 — Pull audio features for both sets

Use `get_candidate_pool` to query the local library, then cross-reference with
`liked_ids` and `disliked_ids`:

```
get_candidate_pool(limit=500)           # all analysed tracks
```

Split the result into:
- `liked_features`: rows whose `ym_id` is in `liked_ids`
- `disliked_features`: rows whose `ym_id` is in `disliked_ids`

If feature coverage is low, call `get_library_stats()` to check
`tracks_with_features` and note the limitation in the report.

---

## Step 4 — Compute statistics per dimension

For each group (liked / disliked) calculate:

| Dimension | What to compute |
|-----------|-----------------|
| Subgenre | Count per subgenre, top-3 over/under-represented |
| BPM | Mean, median, [p10, p90] range |
| Energy (integrated_lufs) | Mean, median, tier distribution |
| Dissonance (dissonance_mean) | Mean — higher = more harmonic tension |
| Danceability | Mean — proxy for groove coefficient |
| Mood | Distribution across classified moods |

Delta = liked_mean - disliked_mean for numeric features.

---

## Step 5 — Synthesise patterns

Identify 3-5 **actionable insights**, e.g.:
- "You like tracks in the 132-138 BPM range 2x more than slower ones"
- "Industrial and raw subgenres are disproportionately disliked"
- "You prefer lower dissonance (≈0.3) — harmonic / hypnotic vibes"
- "Danceability > 2.0 strongly correlates with liked tracks"

Connect insights to set-building implications (energy arc, subgenre flow, key selection).

---

## Step 6 — Write the report

Produce a Markdown report with these sections:

```markdown
# Taste Profile Report

## TL;DR
3-sentence summary of preferences.

## Data
- Liked tracks analysed: N  (M with audio features)
- Disliked tracks analysed: N  (M with audio features)
- Feature coverage: X%

## Subgenre Preferences
...

## BPM Sweet Spot
...

## Energy Profile
...

## Harmonic Signature
...

## Danceability & Groove
...

## Actionable Insights for Set Building
- ...

## Limitations & Next Steps
- Any gaps in coverage
- Tracks worth importing/analysing to improve the model
```

Report the final Markdown inline so the user can copy it."""
        ),
        Message(
            f"Analysing taste profile (focus: {focus}). "
            "Step 1: collecting liked track IDs from YM → "
            '`ym_likes(action="get_liked", limit=200)`...',
            role="assistant",
        ),
    ]
