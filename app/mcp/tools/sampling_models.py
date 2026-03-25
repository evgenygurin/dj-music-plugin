"""Pydantic models for LLM sampling structured output."""

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Search query for YM/Spotify/etc to find similar tracks."""

    query: str = Field(description="Natural language search query")
    rationale: str = Field(description="Why this query will find similar tracks")


class SimilarTrackSearchStrategy(BaseModel):
    """LLM-generated strategy for finding similar tracks."""

    queries: list[SearchQuery] = Field(
        description="3-5 search queries to find similar tracks",
        min_length=3,
        max_length=5,
    )
    focus_areas: list[str] = Field(
        description="Key characteristics to match (mood, energy, artists, subgenre, etc.)"
    )
