"""Personal scoring profile — user-tuned transition formula weights."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from dj_music.models.base import Base, TimestampMixin


class ScoringProfile(Base, TimestampMixin):
    """Per-user scoring weight preferences."""

    __tablename__ = "scoring_profiles"
    __table_args__ = (
        CheckConstraint("bpm_weight >= 0 AND bpm_weight <= 1", name="ck_scoring_bpm"),
        CheckConstraint(
            "harmonic_weight >= 0 AND harmonic_weight <= 1", name="ck_scoring_harmonic"
        ),
        CheckConstraint("energy_weight >= 0 AND energy_weight <= 1", name="ck_scoring_energy"),
        CheckConstraint(
            "spectral_weight >= 0 AND spectral_weight <= 1", name="ck_scoring_spectral"
        ),
        CheckConstraint("groove_weight >= 0 AND groove_weight <= 1", name="ck_scoring_groove"),
        CheckConstraint("timbral_weight >= 0 AND timbral_weight <= 1", name="ck_scoring_timbral"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    bpm_weight: Mapped[float] = mapped_column(default=0.20)
    harmonic_weight: Mapped[float] = mapped_column(default=0.12)
    energy_weight: Mapped[float] = mapped_column(default=0.18)
    spectral_weight: Mapped[float] = mapped_column(default=0.20)
    groove_weight: Mapped[float] = mapped_column(default=0.15)
    timbral_weight: Mapped[float] = mapped_column(default=0.15)
    description: Mapped[str | None] = mapped_column(String(500), default=None)
