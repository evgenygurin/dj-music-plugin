# ruff: noqa: RUF001, RUF002, RUF003
"""score_harmonic — S_h = alpha·key_distance + (1-alpha)·roughness."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from app.domain.transition.weights import CAMELOT_HARMONIC_BASE
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.scoring import ScoringWeights
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.shared.features import TrackFeatures


class ScoreHarmonicResult(BaseModel):
    """Результат score_harmonic: S_h = α·key_score + (1-α)·roughness_score."""

    model_config = ConfigDict(extra="forbid")

    a_id: int = Field(ge=1, description="source track id")
    b_id: int = Field(ge=1, description="target track id")
    alpha: float = Field(ge=0, le=1, description="α для S_h")
    key_distance: int | None = Field(
        default=None, description="Camelot distance 0..7, None if atonal/missing"
    )
    key_score: float = Field(ge=0, le=1, description="гармоническая совместимость 0..1")
    roughness: float | None = Field(
        default=None, ge=0, le=1, description="средняя sensory roughness (dissonance_mean)"
    )
    roughness_score: float = Field(ge=0, le=1, description="1 - roughness")
    S_h: float = Field(ge=0, le=1, description="S_h = α·key_score + (1-α)·roughness_score")


class ScoreTransitionResult(BaseModel):
    """Результат score_transition: S = Σ w·S."""

    model_config = ConfigDict(extra="forbid")

    a_id: int = Field(ge=1)
    b_id: int = Field(ge=1)
    S_harmony: float = Field(ge=0, le=1)
    S_rhythmic: float = Field(ge=0, le=1)
    S_timbral: float = Field(ge=0, le=1)
    S_energy: float = Field(ge=0, le=1)
    S_structure: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1, description="S = Σ w·S")
    weights: ScoringWeights
    harmonic_detail: ScoreHarmonicResult | None = None


def _key_score_and_distance(a: TrackFeatures, b: TrackFeatures) -> tuple[int | None, float]:
    """Вернуть (distance, score) для пары треков.

    Если ключ отсутствует или atonal — distance=None, score=0.5 (нейтрально).
    Иначе camelot_distance -> score через CAMELOT_HARMONIC_BASE.
    """
    if a.key_code is None or b.key_code is None:
        return None, 0.5
    if a.atonality is True or b.atonality is True:
        return None, 0.5
    # низкая уверенность ключа — считаем ненадёжным
    # (floor берём из настроек, но без I/O используем эвристику 0.2)
    if a.key_confidence is not None and a.key_confidence < 0.2:
        return None, 0.5
    if b.key_confidence is not None and b.key_confidence < 0.2:
        return None, 0.5
    try:
        from app.domain.camelot.wheel import camelot_distance

        dist = camelot_distance(int(a.key_code), int(b.key_code))
    except ValueError:
        return None, 0.5
    score = CAMELOT_HARMONIC_BASE.get(dist, 0.0)
    return dist, float(score)


def _roughness_and_score(a: TrackFeatures, b: TrackFeatures) -> tuple[float | None, float]:
    """Roughness proxy: среднее dissonance_mean (0..1). Score = 1 - roughness."""
    da = a.dissonance_mean
    db = b.dissonance_mean
    if da is None and db is None:
        return None, 0.5
    if da is None:
        # один трек без данных — берём второй
        val = float(db)  # type: ignore[arg-type]
        return val, max(0.0, min(1.0, 1.0 - val))
    if db is None:
        val = float(da)
        return val, max(0.0, min(1.0, 1.0 - val))
    avg = (float(da) + float(db)) / 2.0
    avg = max(0.0, min(1.0, avg))
    return avg, max(0.0, min(1.0, 1.0 - avg))


def _compute_s_h(a: TrackFeatures, b: TrackFeatures, alpha: float) -> ScoreHarmonicResult:
    """Чистая функция S_h = α·key_score + (1-α)·roughness_score."""
    # clamp alpha
    alpha = max(0.0, min(1.0, alpha))
    dist, k_score = _key_score_and_distance(a, b)
    rough, r_score = _roughness_and_score(a, b)
    s_h = alpha * k_score + (1.0 - alpha) * r_score
    s_h = max(0.0, min(1.0, s_h))
    # a_id/b_id заполнит вызывающий тул, здесь заглушка 0
    return ScoreHarmonicResult(
        a_id=1,
        b_id=1,
        alpha=alpha,
        key_distance=dist,
        key_score=k_score,
        roughness=rough,
        roughness_score=r_score,
        S_h=s_h,
    )


def _score_rhythmic(a: TrackFeatures, b: TrackFeatures) -> float:
    """S_r — ритмическая совместимость (BPM). 1 - |ΔBPM|/10, drift штраф."""
    if a.bpm is None or b.bpm is None:
        return 0.5
    delta = abs(float(a.bpm) - float(b.bpm))
    base = max(0.0, 1.0 - delta / 10.0)
    # дрейфующий темп — штраф 0.2
    if a.variable_tempo or b.variable_tempo:
        base *= 0.8
    return max(0.0, min(1.0, base))


def _score_timbral(a: TrackFeatures, b: TrackFeatures) -> float:
    """S_t — тембральная близость (mfcc / spectral contrast)."""
    # приоритет: mfcc cosine, иначе spectral_contrast diff
    if a.mfcc_vector and b.mfcc_vector and len(a.mfcc_vector) == len(b.mfcc_vector):
        import math

        dot = sum(x * y for x, y in zip(a.mfcc_vector, b.mfcc_vector, strict=False))
        na = math.sqrt(sum(x * x for x in a.mfcc_vector))
        nb = math.sqrt(sum(x * x for x in b.mfcc_vector))
        if na > 0 and nb > 0:
            cos = dot / (na * nb)
            # cos -1..1 -> 0..1
            return max(0.0, min(1.0, (cos + 1) / 2))
    if a.spectral_contrast is not None and b.spectral_contrast is not None:
        diff = abs(float(a.spectral_contrast) - float(b.spectral_contrast))
        return max(0.0, min(1.0, 1.0 - diff / 15.0))
    if a.spectral_centroid_hz is not None and b.spectral_centroid_hz is not None:
        # fallback: centroid близость
        diff = abs(float(a.spectral_centroid_hz) - float(b.spectral_centroid_hz))
        return max(0.0, min(1.0, 1.0 - diff / 5000.0))
    return 0.5


def _score_energy(a: TrackFeatures, b: TrackFeatures) -> float:
    """S_e — энергетическая совместимость (LUFS). 1 - |ΔLUFS|/6."""
    if a.integrated_lufs is None or b.integrated_lufs is None:
        # fallback energy_mean
        if a.energy_mean is not None and b.energy_mean is not None:
            diff = abs(float(a.energy_mean) - float(b.energy_mean))
            return max(0.0, min(1.0, 1.0 - diff))
        return 0.5
    delta = abs(float(a.integrated_lufs) - float(b.integrated_lufs))
    return max(0.0, min(1.0, 1.0 - delta / 6.0))


def _score_structure(a: TrackFeatures, b: TrackFeatures) -> float:
    """S_s — структурный бонус (phrase)."""
    # если оба имеют phrase_boundaries_ms — бонус за совпадение dominant_phrase_bars
    if a.dominant_phrase_bars is not None and b.dominant_phrase_bars is not None:
        if a.dominant_phrase_bars == b.dominant_phrase_bars:
            return 1.0
        return 0.7
    if a.phrase_boundaries_ms is not None and b.phrase_boundaries_ms is not None:
        return 0.8
    return 0.5


def _compute_transition(
    a: TrackFeatures, b: TrackFeatures, weights: ScoringWeights
) -> tuple[float, float, float, float, float, float, ScoreHarmonicResult]:
    """Вычислить 5 компонентов и overall S = Σ w·S."""
    norm = weights.normalized()
    harm_detail = _compute_s_h(a, b, float(weights.roughness_vs_camelot))
    s_h = harm_detail.S_h
    s_r = _score_rhythmic(a, b)
    s_t = _score_timbral(a, b)
    s_e = _score_energy(a, b)
    s_s = _score_structure(a, b)
    overall = (
        norm["w_harmony"] * s_h
        + norm["w_rhythmic"] * s_r
        + norm["w_timbral"] * s_t
        + norm["w_energy"] * s_e
        + norm["w_structure"] * s_s
    )
    overall = max(0.0, min(1.0, overall))
    return s_h, s_r, s_t, s_e, s_s, overall, harm_detail


@tool(
    name="score_harmonic",
    tags={"namespace:score", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description="S_h = α·key_score + (1-α)·roughness_score (Faraldo + Gebhardt).",
    meta={"timeout_s": 30.0},
    timeout=30.0,
)
async def score_harmonic(
    a_id: Annotated[int, Field(ge=1, description="source track id")],
    b_id: Annotated[int, Field(ge=1, description="target track id")],
    alpha: Annotated[
        float, Field(ge=0, le=1, description="α для S_h, 0=only roughness 1=only Camelot")
    ] = 0.5,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> ScoreHarmonicResult:
    _ = ctx  # unused, kept for FastMCP context parity
    feats = await uow.track_features.get_scoring_features_batch([a_id, b_id])
    a = feats.get(a_id)
    b = feats.get(b_id)
    missing: list[int] = []
    if a is None:
        missing.append(a_id)
    if b is None:
        missing.append(b_id)
    if missing:
        raise ValidationError(
            f"missing scoring features for track_ids={missing}",
            details={"missing_track_ids": missing},
        )
    # cast after None check
    assert a is not None and b is not None
    res = _compute_s_h(a, b, float(alpha))
    # проставить реальные id/alpha
    res.a_id = a_id
    res.b_id = b_id
    res.alpha = float(alpha)
    return res


@tool(
    name="score_transition",
    tags={"namespace:score", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description="S = Σ w·S (5 компонентов, веса ScoringWeights, нормализация Σw=1).",
    meta={"timeout_s": 30.0},
    timeout=30.0,
)
async def score_transition(
    a_id: Annotated[int, Field(ge=1, description="source track id")],
    b_id: Annotated[int, Field(ge=1, description="target track id")],
    weights: Annotated[
        ScoringWeights | None,
        Field(description="веса S=Σw·S, None=дефолт 0.25/0.25/0.2/0.15/0.15"),
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> ScoreTransitionResult:
    _ = ctx
    w = weights or ScoringWeights()
    feats = await uow.track_features.get_scoring_features_batch([a_id, b_id])
    a = feats.get(a_id)
    b = feats.get(b_id)
    missing: list[int] = []
    if a is None:
        missing.append(a_id)
    if b is None:
        missing.append(b_id)
    if missing:
        raise ValidationError(
            f"missing scoring features for track_ids={missing}",
            details={"missing_track_ids": missing},
        )
    assert a is not None and b is not None
    s_h, s_r, s_t, s_e, s_s, overall, detail = _compute_transition(a, b, w)
    detail.a_id = a_id
    detail.b_id = b_id
    return ScoreTransitionResult(
        a_id=a_id,
        b_id=b_id,
        S_harmony=s_h,
        S_rhythmic=s_r,
        S_timbral=s_t,
        S_energy=s_e,
        S_structure=s_s,
        overall=overall,
        weights=w,
        harmonic_detail=detail,
    )


# Pure helpers for unit tests / domain reuse
def score_harmonic_pure(
    a: TrackFeatures, b: TrackFeatures, alpha: float = 0.5
) -> ScoreHarmonicResult:
    """Чистый S_h без I/O (для тестов)."""
    res = _compute_s_h(a, b, alpha)
    return res


def score_transition_pure(
    a: TrackFeatures, b: TrackFeatures, weights: ScoringWeights | None = None
) -> ScoreTransitionResult:
    """Чистый S = Σw·S без I/O (для тестов)."""
    w = weights or ScoringWeights()
    s_h, s_r, s_t, s_e, s_s, overall, detail = _compute_transition(a, b, w)
    return ScoreTransitionResult(
        a_id=1,
        b_id=1,
        S_harmony=s_h,
        S_rhythmic=s_r,
        S_timbral=s_t,
        S_energy=s_e,
        S_structure=s_s,
        overall=overall,
        weights=w,
        harmonic_detail=detail,
    )
