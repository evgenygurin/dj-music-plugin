# ruff: noqa: RUF001, RUF002
"""Scoring schemas: ScoringWeights (Σw=1) + harmonic helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScoringWeights(BaseModel):
    """Веса для S = Σ w·S (harmony/rhythmic/timbral/energy/structure).

    Каждый вес в [0,1], сумма должна быть ≈1.0 (проверяется вручную или
    через :meth:`normalized`). ``roughness_vs_camelot`` — α для S_h.
    """

    model_config = ConfigDict(extra="forbid")

    w_harmony: float = Field(default=0.25, ge=0, le=1, description="вес гармонии S_h")
    w_rhythmic: float = Field(default=0.25, ge=0, le=1, description="вес ритма S_r")
    w_timbral: float = Field(default=0.2, ge=0, le=1, description="вес тембра S_t")
    w_energy: float = Field(default=0.15, ge=0, le=1, description="вес энергии S_e")
    w_structure: float = Field(default=0.15, ge=0, le=1, description="вес структуры S_s")
    roughness_vs_camelot: float = Field(
        default=0.5, ge=0, le=1, description="α для S_h = α·key_distance + (1-α)·roughness"
    )

    def normalized(self) -> dict[str, float]:
        """Вернуть нормализованные веса (Σ=1).

        Делит каждый из 5 весов на сумму, чтобы Σ=1. ``roughness_vs_camelot``
        не входит в сумму — это отдельный α.
        """
        total = (
            self.w_harmony + self.w_rhythmic + self.w_timbral + self.w_energy + self.w_structure
        )
        if total == 0:
            # вырожденный случай — равномерные веса
            equal = 1.0 / 5.0
            return {
                "w_harmony": equal,
                "w_rhythmic": equal,
                "w_timbral": equal,
                "w_energy": equal,
                "w_structure": equal,
            }
        return {
            "w_harmony": self.w_harmony / total,
            "w_rhythmic": self.w_rhythmic / total,
            "w_timbral": self.w_timbral / total,
            "w_energy": self.w_energy / total,
            "w_structure": self.w_structure / total,
        }


class HarmonicProfile(BaseModel):
    """Профиль гармонии трека (для analyzer)."""

    model_config = ConfigDict(extra="forbid")

    track_id: int = Field(ge=1, description="ID трека")
    chroma: list[float] | None = Field(default=None, description="chroma/HPCP вектор")
    roughness: float | None = Field(
        default=None, ge=0, le=1, description="sensory roughness 0..1 (dissonance)"
    )
    key_scores: dict[int, float] | None = Field(
        default=None, description="S_h per key (target_keys -> score)"
    )


class ScoreResult(BaseModel):
    """Результат score_transition: S = Σ w·S."""

    model_config = ConfigDict(extra="forbid")

    a_id: int = Field(ge=1, description="source track")
    b_id: int = Field(ge=1, description="target track")
    S_harmony: float = Field(ge=0, le=1, description="S_h")
    S_rhythmic: float = Field(ge=0, le=1, description="S_r")
    S_timbral: float = Field(ge=0, le=1, description="S_t")
    S_energy: float = Field(ge=0, le=1, description="S_e")
    S_structure: float = Field(ge=0, le=1, description="S_s")
    overall: float = Field(ge=0, le=1, description="S = Σ w·S")
    weights: ScoringWeights = Field(description="использованные веса")


class TransitionScoreSchema(BaseModel):
    """Pydantic-совместимая версия TransitionScore (для MCP)."""

    model_config = ConfigDict(extra="forbid")

    a_id: int = Field(ge=1)
    b_id: int = Field(ge=1)
    bpm: float = Field(ge=0, le=1)
    energy: float = Field(ge=0, le=1)
    drums: float = Field(ge=0, le=1)
    bass: float = Field(ge=0, le=1)
    harmonics: float = Field(ge=0, le=1)
    vocals: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1)
    hard_reject: bool = False
    reject_reason: str | None = None
