"""Taste profile analysis prompt."""

from __future__ import annotations

from typing import Annotated

from fastmcp.prompts import Message, PromptResult, prompt
from pydantic import Field


@prompt(
    name="taste_analysis",
    title="Taste Profile Analysis",
    description=(
        "Analyze the user's music taste based on liked/disliked tracks. "
        "Produces a structured report with subgenre preferences, BPM ranges, "
        "energy patterns, and actionable insights for set building."
    ),
    tags={"sets", "workflow"},
    meta={"version": "1.0"},
)
def taste_analysis(
    limit: Annotated[int, Field(description="Max tracks to analyze")] = 500,
) -> PromptResult:
    """Analyze user's taste profile from liked and disliked tracks."""
    return PromptResult(
        messages=[
            Message(
                f"Analyze the user's music taste profile (up to {limit} tracks):\n\n"
                f"1. **Collect liked tracks**: `ym_likes(action='get_liked')` — "
                f"paginate until truncated=False\n"
                f"2. **Identify dislikes**: `filter_by_feedback(ym_track_ids=<local_ids>)` "
                f"to get banned/boosted tracks\n"
                f"3. **Pull audio features**: `get_candidate_pool(limit={limit})` and "
                f"cross-reference with liked/disliked sets\n"
                f"4. **Compare dimensions**:\n"
                f"   - Subgenre distribution (liked vs disliked)\n"
                f"   - BPM range preferences\n"
                f"   - Energy (LUFS) patterns\n"
                f"   - Spectral characteristics (dissonance, flatness)\n"
                f"   - Danceability scores\n"
                f"5. **Report**: Structured Markdown with:\n"
                f"   - TL;DR (3 sentences)\n"
                f"   - Per-dimension comparison tables\n"
                f"   - Actionable set-building insights\n"
                f"   - Discovery recommendations based on patterns"
            ),
        ],
        description=f"Taste profile analysis (up to {limit} tracks)",
    )
