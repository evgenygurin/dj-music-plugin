"""ArcCritique — structured LLM output for set arc narrative."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArcCritique(BaseModel):
    """Structured narrative critique of a DJ set arc, generated via ctx.sample().

    Used as ``result_type`` in ``ctx.sample()`` — FastMCP handles JSON
    validation and auto-retry if the LLM returns an invalid response.
    """

    crowd_journey: str = Field(
        description=(
            "Narrative description of crowd experience across the set phases. "
            "E.g. 'Opens hypnotic 130 BPM → industrial build at 5–8 → peak at 10 → release'"
        )
    )
    weak_transitions: list[str] = Field(
        description=(
            "List of specific transition problems. Empty list means no weak spots. "
            "E.g. ['Track 8→9: same BPM and energy, no dynamic shift']"
        )
    )
    strongest_moment: str = Field(
        description="The single track position with highest expected crowd response."
    )
    recommendation: str = Field(
        description=(
            "One concrete improvement suggestion, or 'No changes needed' if arc is solid."
        )
    )
