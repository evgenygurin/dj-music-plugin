"""TrackFeedback DTOs."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrackFeedbackView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = None
    notes: str | None = None


class TrackFeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    kind__eq: Literal["like", "ban", "rate"] | None = None
    kind__in: list[Literal["like", "ban", "rate"]] | None = None
    # rating: full numeric lookups - "find tracks rated >= 4" was the
    # canonical query and used to be rejected (audit iter 6).
    rating__eq: int | None = None
    rating__gte: int | None = None
    rating__lte: int | None = None
    rating__in: list[int] | None = None


class TrackFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_kind_rating_pairing(self) -> Self:
        # Audit iter 60 (T-58): the ``kind`` and ``rating`` fields
        # have a strict semantic relationship that the previous schema
        # didn't enforce:
        # - kind="rate"  → rating REQUIRED (1-5)
        # - kind="like"  → rating MUST be absent (binary signal)
        # - kind="ban"   → rating MUST be absent (binary signal)
        # Without this, ``entity_create(track_feedback, {kind: "rate"})``
        # would persist with rating=null (a "rate" with no rating);
        # ``{kind: "like", rating: 5}`` would persist a stray rating
        # alongside a binary like — both broke downstream consumers.
        if self.kind == "rate" and self.rating is None:
            raise ValueError("kind='rate' requires a rating value (1-5)")
        if self.kind in {"like", "ban"} and self.rating is not None:
            raise ValueError(f"kind={self.kind!r} is binary; rating must be absent")
        return self


class TrackFeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
