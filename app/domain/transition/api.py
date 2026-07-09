from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from app.domain.transition.enums import (
        NeuralMixTransition,
        SubgenrePairType,
        TransitionIntent,
    )
    from app.domain.transition.picker import PickerDecision
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures

    class FeatureArrays(Protocol):
        """Pre-extracted feature arrays for batch (vectorised) scoring.

        Implemented by the bulk scorer to pass cached float/bool/int
        arrays to ``ScoringComponent.score_pairs`` and
        ``HardConstraint.check_bulk`` so individual feature lookups are
        not repeated inside the vectorised hot loop.
        """

        bpm: FloatArr
        key_code: IntArr
        integrated_lufs: FloatArr
        pitch_salience: FloatArr
        spectral_centroid: FloatArr
        tonnetz_1: FloatArr
        tonnetz_2: FloatArr
        tonnetz_3: FloatArr
        tonnetz_4: FloatArr
        tonnetz_5: FloatArr
        tonnetz_6: FloatArr
        energy_band_0: FloatArr
        energy_band_1: FloatArr
        energy_band_2: FloatArr
        energy_band_3: FloatArr
        energy_band_4: FloatArr
        energy_band_5: FloatArr
        latent_1: FloatArr
        latent_2: FloatArr
        latent_3: FloatArr
        latent_4: FloatArr
        latent_5: FloatArr
        latent_6: FloatArr
        latent_7: FloatArr
        latent_8: FloatArr
        latent_9: FloatArr
        latent_10: FloatArr
        latent_11: FloatArr
        latent_12: FloatArr
        latent_13: FloatArr
        latent_14: FloatArr
        latent_15: FloatArr
        latent_16: FloatArr
        latent_17: FloatArr
        latent_18: FloatArr
        latent_19: FloatArr
        latent_20: FloatArr


FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]
BoolArr = npt.NDArray[np.bool_]


@runtime_checkable
class ScoringComponent(Protocol):
    name: str
    default_weight: float

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float: ...
    def score_pairs(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr: ...


@runtime_checkable
class HardConstraint(Protocol):
    name: str

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> str | None: ...

    def check_bulk(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> BoolArr: ...


@runtime_checkable
class WeightOverlay(Protocol):
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]: ...


@runtime_checkable
class PickerRule(Protocol):
    name: str
    confidence: float

    def evaluate(
        self,
        score: TransitionScore,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        section_context: SectionContext | None,
        subgenre_pair: SubgenrePairType | None,
        intent: TransitionIntent | None,
    ) -> PickerDecision | None: ...


@runtime_checkable
class VocalActivityDetector(Protocol):
    def is_active(self, t: TrackFeatures) -> bool: ...
    def is_low(self, t: TrackFeatures) -> bool: ...
    def data_missing(self, t: TrackFeatures) -> bool: ...


@runtime_checkable
class HarmonicMotifDetector(Protocol):
    def is_motif(self, t: TrackFeatures) -> bool: ...


@runtime_checkable
class RecipeBuilder(Protocol):
    transition: NeuralMixTransition

    def build(self, bars: int) -> tuple[tuple[object, ...], tuple[object, ...]]: ...


class TransitionEvaluatorProtocol(Protocol):
    def evaluate(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> TransitionScore: ...
