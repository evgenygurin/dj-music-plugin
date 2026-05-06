"""Custom scoring weight profile."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScoringProfile(Base, TimestampMixin):
    __tablename__ = "scoring_profiles"
    __table_args__ = (
        CheckConstraint("bpm_weight BETWEEN 0 AND 1", name="ck_profile_bpm"),
        CheckConstraint("energy_weight BETWEEN 0 AND 1", name="ck_profile_energy"),
        CheckConstraint("drums_weight BETWEEN 0 AND 1", name="ck_profile_drums"),
        CheckConstraint("bass_weight BETWEEN 0 AND 1", name="ck_profile_bass"),
        CheckConstraint("harmonics_weight BETWEEN 0 AND 1", name="ck_profile_harmonics"),
        CheckConstraint("vocals_weight BETWEEN 0 AND 1", name="ck_profile_vocals"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    bpm_weight: Mapped[float] = mapped_column()
    harmonics_weight: Mapped[float] = mapped_column()
    energy_weight: Mapped[float] = mapped_column()
    bass_weight: Mapped[float] = mapped_column()
    drums_weight: Mapped[float] = mapped_column()
    vocals_weight: Mapped[float] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
