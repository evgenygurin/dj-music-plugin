"""Custom scoring weight profile."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScoringProfile(Base, TimestampMixin):
    __tablename__ = "scoring_profiles"
    __table_args__ = (
        CheckConstraint("bpm_weight BETWEEN 0 AND 1", name="ck_profile_bpm"),
        CheckConstraint("harmonic_weight BETWEEN 0 AND 1", name="ck_profile_harm"),
        CheckConstraint("energy_weight BETWEEN 0 AND 1", name="ck_profile_energy"),
        CheckConstraint("spectral_weight BETWEEN 0 AND 1", name="ck_profile_spectral"),
        CheckConstraint("groove_weight BETWEEN 0 AND 1", name="ck_profile_groove"),
        CheckConstraint("timbral_weight BETWEEN 0 AND 1", name="ck_profile_timbral"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    bpm_weight: Mapped[float] = mapped_column()
    harmonic_weight: Mapped[float] = mapped_column()
    energy_weight: Mapped[float] = mapped_column()
    spectral_weight: Mapped[float] = mapped_column()
    groove_weight: Mapped[float] = mapped_column()
    timbral_weight: Mapped[float] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
