"""Tests for discovery MCP tools with sampling.

NOTE: FastMCP Client tests are disabled due to typing_extensions TypeForm import issue.
Testing Pydantic models and basic functionality instead.
"""

from __future__ import annotations

import pytest

from app.mcp.tools.sampling_models import SearchQuery, SimilarTrackSearchStrategy

# NOTE: Integration tests disabled due to typing_extensions issue with FastMCP Client
# When FastMCP fixes the key_value dependency issue, uncomment these tests


# ── Pydantic Model Validation ────────────────────────


def test_search_query_model():
    """SearchQuery Pydantic model validates correctly."""
    query = SearchQuery(
        query="minimal techno 130 BPM",
        rationale="Match tempo and mood",
    )
    assert query.query == "minimal techno 130 BPM"
    assert query.rationale == "Match tempo and mood"


def test_similar_track_search_strategy_model():
    """SimilarTrackSearchStrategy Pydantic model validates correctly."""
    strategy = SimilarTrackSearchStrategy(
        queries=[
            SearchQuery(query="q1", rationale="r1"),
            SearchQuery(query="q2", rationale="r2"),
            SearchQuery(query="q3", rationale="r3"),
        ],
        focus_areas=["energy", "BPM"],
    )
    assert len(strategy.queries) == 3
    assert len(strategy.focus_areas) == 2


def test_similar_track_search_strategy_min_queries():
    """SimilarTrackSearchStrategy requires at least 3 queries."""
    with pytest.raises(ValueError, match="at least 3"):
        SimilarTrackSearchStrategy(
            queries=[
                SearchQuery(query="q1", rationale="r1"),
                SearchQuery(query="q2", rationale="r2"),
            ],
            focus_areas=["energy"],
        )


def test_similar_track_search_strategy_max_queries():
    """SimilarTrackSearchStrategy allows max 5 queries."""
    with pytest.raises(ValueError, match="at most 5"):
        SimilarTrackSearchStrategy(
            queries=[SearchQuery(query=f"q{i}", rationale=f"r{i}") for i in range(6)],
            focus_areas=["energy"],
        )
